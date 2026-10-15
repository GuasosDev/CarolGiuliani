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

# 5) Traer la primera pagina (15 filas) con select_related + Exists
def _page():
    from django.db.models import Exists, OuterRef
    from communications.models import EmailAttachment
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
_t("primera pagina (15 filas) select_related+Exists+order", _page)

# 6) _get_conversation_counts completo (dispara ~7 counts sobre el mismo base_qs)
_t("_get_conversation_counts()  [todos los conteos sidebar]",
   lambda: _get_conversation_counts(user))

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

# EXPLAIN de las dos candidatas principales
_explain(
    "conversations IN(subquery) distinct",
    get_agent_conversations(user).filter(
        id__in=EmailMessage.objects.filter(email_account=ua).values_list(
            "message__conversation_id", flat=True
        )
    ).distinct(),
)
