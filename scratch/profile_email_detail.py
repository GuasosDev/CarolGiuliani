"""
Perfil de la apertura de un email (email_message_detail) en MariaDB.

Detecta CUAAL etapa se come el tiempo/CPU al hacer clic en un asunto:
 - las consultas de la vista,
 - _find_sibling_outbound_bcc (LIKE %mid% + filesort sobre TODO el outbound),
 - limpiar_email_html (CPU puro, si cleaned_html esta vacio).

Uso:
    python manage.py shell -c "import sys; sys.argv=['x','npalacios']; exec(open('scratch/profile_email_detail.py').read())"
    # para un email concreto:
    python manage.py shell -c "import sys; sys.argv=['x','npalacios','12345']; exec(open('scratch/profile_email_detail.py').read())"
"""
import sys
import time

from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.test.utils import CaptureQueriesContext
from django.contrib.auth import get_user_model

from communications.models import EmailMessage, Message
from communications.views import (
    _get_user_email_account,
    _get_conversation_counts,
    _reply_all_recipients,
    _email_header_recipients,
    _email_message_body_html,
    _email_reply_quote_html,
    _email_compose_recipient_catalog,
    get_agent_conversations,
)

User = get_user_model()


def _arg(name, default):
    try:
        return int(name)
    except (TypeError, ValueError):
        return default


username = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] not in ("", "-c") else "npalacios"
pk_arg = sys.argv[2] if len(sys.argv) > 2 else None

user = User.objects.get(username=username)
ua = _get_user_email_account(user)
print("USER   =", user.username)
print("ACCT   =", ua.email_address if ua else None)
print("ENGINE =", settings.DATABASES["default"]["ENGINE"])
print("=" * 70)


def _t(label, fn):
    t0 = time.perf_counter()
    res = fn()
    dt = (time.perf_counter() - t0) * 1000
    print(f"{dt:10.1f} ms  {label}")
    return res


def _explain(label, sql, params=()):
    print(f"\n--- EXPLAIN: {label} ---")
    try:
        with connection.cursor() as cur:
            cur.execute("EXPLAIN " + sql, params)
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()
            w = [max(len(str(c)), *(len(str(r[i])) for r in rows)) if rows else len(str(c))
                 for i, c in enumerate(cols)]
            print(" | ".join(str(c).ljust(w[i]) for i, c in enumerate(cols)))
            for r in rows:
                print(" | ".join(("" if v is None else str(v)).ljust(w[i]) for i, v in enumerate(r)))
    except Exception as e:
        print("   EXPLAIN fallo:", e)


# ------------------------------------------------------------------
# Elegir el email que el usuario abriria: el mas reciente de su casilla
# (que es lo que se clickea), o el pk pasado por argv.
# ------------------------------------------------------------------
if pk_arg:
    em = EmailMessage.objects.select_related(
        'message', 'message__conversation', 'email_account'
    ).get(pk=int(pk_arg))
else:
    em = (
        EmailMessage.objects.select_related(
            'message', 'message__conversation', 'email_account'
        )
        .filter(email_account=ua)
        .order_by('-email_date')
        .first()
    )
if not em:
    raise SystemExit("No hay emails para esta cuenta")

conv = em.message.conversation
print(f"EMAIL  pk={em.pk} subject={str(em.subject)[:60]!r}")
print(f"CONV   pk={conv.pk}  direction={em.message.direction}")
print("=" * 70)

# ------------------------------------------------------------------
# Tamano del problema: cuantos salientes hay en TOTAL (escaneo de _find_sibling)
# ------------------------------------------------------------------
n_out = _t("COUNT EmailMessage outbound (global)",
           lambda: EmailMessage.objects.filter(message__direction='outbound').count())
print(f"   -> {n_out} filas candidiales a escanear por _find_sibling_outbound_bcc")

# ------------------------------------------------------------------
# 1) El perm check de la vista
# ------------------------------------------------------------------
_t("perm: get_agent_conversations().filter(pk=conv).exists()",
   lambda: get_agent_conversations(user).filter(pk=conv.pk).exists())

# ------------------------------------------------------------------
# 2) Marca leido (UPDATE por PK, deberia ser ~0)
# ------------------------------------------------------------------
_t("UPDATE Message.is_read (por PK)",
   lambda: Message.objects.filter(pk=em.message.pk).update(is_read=True))

# ------------------------------------------------------------------
# 3) Carga del hilo completo: todos los mensajes email de la conversacion
# ------------------------------------------------------------------
def _load_thread():
    return list(
        Message.objects.select_related('email_data', 'sender')
        .filter(conversation=conv, message_type='email')
        .order_by('created_at')
    )


thread = _t("carga del HILO (Message conv+email_type, select_related email_data)", _load_thread)
print(f"   -> {len(thread)} mensajes en el hilo")

# cuantos EmailAttachment (prefetch N+1?)
_t("  prefetch attachments del hilo",
   lambda: EmailMessage.objects.filter(
       message__in=[m.pk for m in thread]
   ).prefetch_related('attachments').count())

# ------------------------------------------------------------------
# 4) *** Sospechoso principal ***  _find_sibling_outbound_bcc
#    Se dispara desde _reply_all_recipients Y _email_header_recipients
# ------------------------------------------------------------------
print("\n" + "-" * 70)
print("ETAPA SOSPECHOSA: _find_sibling_outbound_bcc (se llama 2 veces por clic)")
print("-" * 70)

with CaptureQueriesContext(connection) as ctx:
    _t("_reply_all_recipients(em)  [dispara sibling outbound]",
       lambda: _reply_all_recipients(em, ua.email_address if ua else ''))
n1 = len(ctx.captured_queries)

with CaptureQueriesContext(connection) as ctx2:
    _t("_email_header_recipients(em)  [dispara sibling outbound otra vez]",
       lambda: _email_header_recipients(em))
n2 = len(ctx2.captured_queries)

print(f"   -> queries: _reply_all_recipients={n1}  _email_header_recipients={n2}")

# El mid real: si es muy corto, LIKE '%x%' casa con TODO y eso explicaria todo.
mid_raw = getattr(em, 'email_message_id', None) or ''
from communications.utils.email_threading import clean_message_id
mid = clean_message_id(mid_raw)
print(f"   -> email_message_id raw len={len(str(mid_raw))}  mid len={len(mid)}  valor={mid[:120]!r}")

# Isolar SQL-puro vs ORM/Python: el MISMO query via cursor (solo em.id, sin
# select_related => sin bajar html_body/cleaned_html/metadata).
with CaptureQueriesContext(connection) as ctx3:
    _t("ORM: qs.filter(mid_q)[:8]  (select_related, baja blobs)",
       lambda: list(
           EmailMessage.objects.filter(message__direction='outbound')
           .exclude(pk=em.pk)
           .select_related('message')
           .order_by('-message__created_at')
           .filter(Q(email_message_id=mid) | Q(email_message_id=f'<{mid}>')
                   | Q(email_message_id__icontains=mid))[:8]
       ))
if ctx3.captured_queries:
    _sql3 = ctx3.captured_queries[-1]['sql']
    t0 = time.perf_counter()
    with connection.cursor() as cur:
        cur.execute(_sql3)
        _rows = cur.fetchall()
    print(f"{(time.perf_counter()-t0)*1000:10.1f} ms  SQL PURO (mismo query via cursor) -> {_rows and len(_rows)} filas")

# Cuantas filas casa realmente el LIKE
if mid:
    t0 = time.perf_counter()
    with connection.cursor() as cur:
        cur.execute(
            """SELECT COUNT(*) FROM communications_emailmessage em
               JOIN communications_message m ON m.id = em.message_id
               WHERE m.direction='outbound'
                 AND (em.email_message_id = %s OR em.email_message_id = %s
                      OR em.email_message_id LIKE CONCAT('%%', %s, '%%'))""",
            [mid, f'<{mid}>', mid],
        )
        _hits = cur.fetchone()[0]
    print(f"{(time.perf_counter()-t0)*1000:10.1f} ms  filas que casan con el mid -> {_hits}")

if mid:
    _explain(
        "sibling outbound: direction+icontains(email_message_id) ORDER BY created_at",
        """
        SELECT em.id
        FROM communications_emailmessage em
        JOIN communications_message m ON m.id = em.message_id
        WHERE m.direction = 'outbound' AND em.id <> %s
          AND (em.email_message_id = %s OR em.email_message_id = %s
               OR em.email_message_id LIKE CONCAT('%%', %s, '%%'))
        ORDER BY m.created_at DESC
        LIMIT 8
        """,
        [em.pk, mid, f'<{mid}>', mid],
    )

# ------------------------------------------------------------------
# 5) Limpieza HTML: CPU puro. Cuantificar cuanto falta por limpiar.
# ------------------------------------------------------------------
print("\n" + "-" * 70)
print("ETAPA CPU: limpiar_email_html (depende de cuantos cleaned_html esten vacios)")
print("-" * 70)
pending = _t("COUNT EmailMessage del hilo SIN cleaned_html",
             lambda: EmailMessage.objects.filter(
                 message__in=[m.pk for m in thread]
             ).filter(Q(cleaned_html='') | Q(cleaned_html__isnull=True)).count())
print(f"   -> {pending}/{len(thread)} mensajes del hilo hay que sanitizarlos")

# tamano real de los cuerpos: es lo que determina el costo de bleach+bs4
sizes = _t("medir len(html_body) del hilo",
           lambda: [len(str(m.email_data.html_body or ''))
                    for m in thread if getattr(m, 'email_data', None)])
print(f"   -> bytes HTML por mensaje: {sizes}")

t0 = time.perf_counter()
_email_message_body_html(em)
print(f"{(time.perf_counter()-t0)*1000:10.1f} ms  _email_message_body_html(em)  "
      f"(cleaned_html {'OCCUPI' if em.cleaned_html else 'VACIO -> sanitiza'})")

# ------------------------------------------------------------------
# 6) Resto de consultas de la vista
# ------------------------------------------------------------------
print("\n" + "-" * 70)
print("RESTO")
print("-" * 70)
_t("_get_conversation_counts(user)", lambda: _get_conversation_counts(user))
_t("_email_compose_recipient_catalog()", lambda: _email_compose_recipient_catalog())

# ------------------------------------------------------------------
# 7) End-to-end REAL: la URL que se clickea
# ------------------------------------------------------------------
print("\n" + "-" * 70)
print("END-TO-END REAL (es lo que el usuario siente)")
print("-" * 70)
try:
    if "testserver" not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append("testserver")
    c = None  # noqa (el Client se importa abajo)
    from django.test import Client
    tc = Client()
    tc.force_login(user)
    url = f"/communications/email-message/{em.pk}/"
    for i in range(3):
        t0 = time.perf_counter()
        r = tc.get(url)
        print(f"{(time.perf_counter()-t0)*1000:10.1f} ms  GET {url}  (status={r.status_code}) "
              f"{'[1ra=fria]' if i == 0 else '[tibia]'}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("end-to-end fallo:", e)

print("=" * 70)
print("Total emails en la casilla y con cleaned_html poblado:")
with connection.cursor() as cur:
    cur.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN cleaned_html IS NULL OR cleaned_html='' THEN 1 ELSE 0 END) AS sin_clean
        FROM communications_emailmessage
        WHERE email_account_id = %s
        """,
        [ua.id],
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    for c_, v in zip(cols, row):
        print(f"   {c_} = {v}")
