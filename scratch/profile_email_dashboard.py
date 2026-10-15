"""
Perfil de lentitud del listado de emails (canal email) en MySQL.

Uso:
    python manage.py shell -c "exec(open('scratch/profile_email_dashboard.py').read())"
    # o con un usuario concreto:
    python manage.py shell -c "import sys; sys.argv=['x','<username>']; exec(open('scratch/profile_email_dashboard.py').read())"

Imprime el tiempo de cada etapa de la vista del dashboard (canal email) y un
EXPLAIN de las consultas candidatas, para saber exactamente dónde se va el tiempo.
"""
import sys
import time

from django.conf import settings
from django.db import connection

from communications.models import EmailMessage, Conversation
from communications.views import (
    _get_user_email_account,
    _get_conversation_counts,
    get_agent_conversations,
)
from django.contrib.auth import get_user_model

User = get_user_model()


def _pick_user():
    if len(sys.argv) > 1 and sys.argv[1] not in ("", "-c"):
        return User.objects.get(username=sys.argv[1])
    # primer usuario activo con casilla email
    for u in User.objects.filter(is_active=True):
        if _get_user_email_account(u):
            return u
    return User.objects.filter(is_superuser=True).first()


def _t(label, fn):
    t0 = time.perf_counter()
    result = fn()
    dt = (time.perf_counter() - t0) * 1000  # ms
    print(f"{dt:9.1f} ms  {label}")
    return result


def _explain(label, qs):
    print(f"\n--- EXPLAIN: {label} ---")
    sql, params = qs.query.sql_with_params()
    try:
        with connection.cursor() as cur:
            cur.execute("EXPLAIN " + sql, params)
            cols = [c[0] for c in cur.description]
            print(" | ".join(cols))
            for row in cur.fetchall():
                print(" | ".join("" if v is None else str(v) for v in row))
    except Exception as e:
        print("EXPLAIN falló:", e)


user = _pick_user()
ua = _get_user_email_account(user)
print("USER   =", user.username)
print("ACCT   =", ua.email_address if ua else None)
print("ENGINE =", settings.DATABASES["default"]["ENGINE"])
print("Es supervisor/superuser:",
      user.is_superuser or user.groups.filter(name="Supervisor").exists())
print("=" * 70)

# 1) Conversaciones base del agente
base_qs = _t("get_agent_conversations().count()",
             lambda: get_agent_conversations(user).count())

# 2) Subquery de ids de conversacion de la casilla (el insumo del IN)
def _ids():
    return list(
        EmailMessage.objects.filter(email_account=ua)
        .values_list("message__conversation_id", flat=True)
    )
ids = _t("list(email_conversation_ids)  [subquery IN]", _ids)
print("   -> ids devueltos:", len(ids))

# 3) conversations filtradas por IN(subquery) + distinct  (como en la vista)
conv_filtered = _t(
    "conversations.filter(id__in=<qs>).distinct().count()",
    lambda: get_agent_conversations(user).filter(
        id__in=EmailMessage.objects.filter(email_account=ua).values_list(
            "message__conversation_id", flat=True
        )
    ).distinct().count(),
)
print("   -> conversaciones visibles:", conv_filtered)

# 4) El COUNT del Paginator sobre las filas de email (inbox)
def _rows_count():
    qs = (
        EmailMessage.objects.select_related("message", "email_account")
        .filter(
            message__conversation__in=get_agent_conversations(user).filter(
                id__in=EmailMessage.objects.filter(email_account=ua).values_list(
                    "message__conversation_id", flat=True
                )
            ).distinct(),
            email_account=ua,
            message__direction="inbound",
        )
    )
    return qs.count()
_t("email_rows_qs.count()  [COUNT paginador, doble subquery]", _rows_count)

# 5) Primera pagina con la forma NUEVA de la vista (Subquery LIMIT + indice)
from django.db.models import Exists, OuterRef, Q, Subquery
from communications.models import EmailAttachment, Conversation

# Forma NUEVA (igual que la vista): visibilidad como subconsulta correlacionada
# CON LIMIT. El LIMIT impide que MariaDB la aplane a semijoin, asi EmailMessage
# conduce con emailmsg_acct_date_idx y el ORDER BY -email_date no hace filesort.
if user.is_superuser or user.groups.filter(name="Supervisor").exists():
    vis_qs = Conversation.objects.all()
else:
    vis_qs = Conversation.objects.filter(
        Q(assigned_to=user) | Q(assigned_to__isnull=True)
    )
vis_qs = vis_qs.filter(channel="email").exclude(status="closed")


def _build_new_qs():
    return (
        EmailMessage.objects.select_related(
            "message", "message__conversation",
            "message__conversation__contact",
            "message__conversation__contact__client",
            "email_account",
        )
        .filter(email_account=ua)
        .annotate(
            _visible_conv_pk=Subquery(
                vis_qs.filter(pk=OuterRef("message__conversation_id")).values("pk")[:1]
            )
        )
        .filter(_visible_conv_pk__isnull=False)
        .filter(message__direction="inbound")
        .annotate(has_attachments=Exists(
            EmailAttachment.objects.filter(email_message_id=OuterRef("pk"))))
        .order_by("-email_date")
    )


def _page_new():
    return len(list(_build_new_qs()[:15]))


_t("primera pagina NUEVA (Subquery LIMIT + indice)", _page_new)

# 5b) Forma VIEJA para comparar (subquery anidado en el IN)
def _page_old():
    qs = (
        EmailMessage.objects.select_related(
            "message", "message__conversation",
            "message__conversation__contact",
            "message__conversation__contact__client",
            "email_account",
        )
        .filter(
            message__conversation__in=get_agent_conversations(user).filter(
                id__in=EmailMessage.objects.filter(email_account=ua).values_list(
                    "message__conversation_id", flat=True
                )
            ).distinct(),
            email_account=ua,
            message__direction="inbound",
        )
        .annotate(has_attachments=Exists(
            EmailAttachment.objects.filter(email_message_id=OuterRef("pk"))))
        .order_by("-email_date")[:15]
    )
    return len(list(qs))
_t("primera pagina VIEJA (subquery anidado) [referencia]", _page_old)

# 6) _get_conversation_counts completo (dispara ~7 counts sobre el mismo base_qs)
_t("_get_conversation_counts()  [todos los conteos sidebar]",
   lambda: _get_conversation_counts(user))

# 7) End-to-end REAL sobre la vista ya parcheada (test client)
try:
    from django.test import Client
    if "testserver" not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append("testserver")
    c = Client()
    c.force_login(user)
    _t("GET /communications/?channel=email  [VISTA REAL end-to-end]",
       lambda: c.get("/communications/?channel=email").status_code)
except Exception as e:
    print("end-to-end fallo:", e)

print("=" * 70)
print("ÍNDICES en communications_emailmessage:")
with connection.cursor() as cur:
    try:
        cur.execute("SHOW INDEX FROM communications_emailmessage")
        for r in cur.fetchall():
            # Key_name, Column_name, Non_unique
            print(f"   {r[2]:35s} col={r[4]:25s} unique={'NO' if r[1] else 'YES'}")
    except Exception as e:
        print("   no se pudo listar:", e)

# EXPLAIN de la consulta REAL que genera el ORM (verifica el LIMIT en la subconsulta)
_sql, _params = _build_new_qs().query.sql_with_params()
print("\n--- SQL que genera el ORM (nueva) ---")
print(_sql)
_explain(
    "PAGE nueva (Subquery LIMIT): account + subquery(conv visible)[:1] + direction ORDER BY email_date",
    _build_new_qs(),
)
