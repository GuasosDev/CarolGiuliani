"""
Test de planes de ejecucion (MariaDB) para el inbox de email.
Prueba varias formas de la MISMA consulta y muestra cual usa el indice
emailmsg_acct_date_idx y elimina "Using filesort".

Uso:
    python manage.py shell -c "import sys; sys.argv=['x','npalacios']; exec(open('scratch/explain_plans.py').read())"
"""
import sys

from django.db import connection
from django.contrib.auth import get_user_model

from communications.models import EmailAccount

User = get_user_model()

username = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] not in ("", "-c") else "npalacios"
user = User.objects.get(username=username)
acct = EmailAccount.objects.filter(is_active=True, user=user).first()
if not acct:
    raise SystemExit(f"Sin EmailAccount activa para {username}")

ua_id = acct.id
u_id = user.id
print(f"user={username} id={u_id}  email_account_id={ua_id}\n" + "=" * 70)


def run(label, sql, params=()):
    print(f"\n### {label}")
    try:
        with connection.cursor() as cur:
            cur.execute("EXPLAIN " + sql, params)
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()
            w = [max(len(str(c)), *(len(str(r[i])) for r in rows)) if rows else len(str(c)) for i, c in enumerate(cols)]
            print(" | ".join(str(c).ljust(w[i]) for i, c in enumerate(cols)))
            for r in rows:
                print(" | ".join(("" if v is None else str(v)).ljust(w[i]) for i, v in enumerate(r)))
        # tiempo real de la consulta (sin EXPLAIN)
        import time
        with connection.cursor() as cur:
            t0 = time.perf_counter()
            cur.execute(sql, params)
            cur.fetchall()
            print(f"    -> tiempo real: {(time.perf_counter()-t0)*1000:.1f} ms")
    except Exception as e:
        print("   ERROR:", e)


# 1) Forma actual (JOIN implicito del ORM con EXISTS): baseline
run(
    "1) JOIN plano (conversation -> message -> emailmessage) ORDER BY email_date",
    """
    SELECT em.id
    FROM communications_emailmessage em
    JOIN communications_message m ON m.id = em.message_id
    JOIN communications_conversation c ON c.id = m.conversation_id
    WHERE em.email_account_id = %s
      AND m.direction = 'inbound'
      AND c.channel = 'email'
      AND c.status <> 'closed'
      AND (c.assigned_to_id = %s OR c.assigned_to_id IS NULL)
    ORDER BY em.email_date DESC
    LIMIT 15
    """,
    [ua_id, u_id],
)

# 2) STRAIGHT_JOIN: fuerza que emailmessage sea la tabla conductora
run(
    "2) STRAIGHT_JOIN (emailmessage primero)",
    """
    SELECT STRAIGHT_JOIN em.id
    FROM communications_emailmessage em
    JOIN communications_message m ON m.id = em.message_id
    JOIN communications_conversation c ON c.id = m.conversation_id
    WHERE em.email_account_id = %s
      AND m.direction = 'inbound'
      AND c.channel = 'email'
      AND c.status <> 'closed'
      AND (c.assigned_to_id = %s OR c.assigned_to_id IS NULL)
    ORDER BY em.email_date DESC
    LIMIT 15
    """,
    [ua_id, u_id],
)

# 3) emailmessage + EXISTS correlacionado (sin JOIN a conversation)
run(
    "3) emailmessage + EXISTS(conv) + JOIN message",
    """
    SELECT em.id
    FROM communications_emailmessage em
    JOIN communications_message m ON m.id = em.message_id
    WHERE em.email_account_id = %s
      AND m.direction = 'inbound'
      AND EXISTS (
        SELECT 1 FROM communications_conversation c
        WHERE c.id = m.conversation_id
          AND c.channel = 'email'
          AND c.status <> 'closed'
          AND (c.assigned_to_id = %s OR c.assigned_to_id IS NULL)
      )
    ORDER BY em.email_date DESC
    LIMIT 15
    """,
    [ua_id, u_id],
)

# 4) Solo emailmessage (sin conversation) para ver el plan "ideal" del indice
run(
    "4) SOLO emailmessage+message (sin filtro conversation) -> plan ideal",
    """
    SELECT em.id
    FROM communications_emailmessage em
    JOIN communications_message m ON m.id = em.message_id
    WHERE em.email_account_id = %s
      AND m.direction = 'inbound'
    ORDER BY em.email_date DESC
    LIMIT 15
    """,
    [ua_id],
)

# 5) Subconsulta correlacionada con LIMIT (lo que emitiria el ORM con
#    Subquery(...values('pk')[:1]) + isnull=False). El LIMIT impide que
#    MariaDB la aplane a semijoin -> emailmessage conduce con el indice.
run(
    "5) Subquery correlacionada con LIMIT (forma ORM objetivo)",
    """
    SELECT em.id
    FROM communications_emailmessage em
    JOIN communications_message m ON m.id = em.message_id
    WHERE em.email_account_id = %s
      AND m.direction = 'inbound'
      AND (SELECT c.id FROM communications_conversation c
           WHERE c.channel = 'email'
             AND c.status <> 'closed'
             AND (c.assigned_to_id = %s OR c.assigned_to_id IS NULL)
             AND c.id = m.conversation_id
           LIMIT 1) IS NOT NULL
    ORDER BY em.email_date DESC
    LIMIT 15
    """,
    [ua_id, u_id],
)

print("\n" + "=" * 70)
print("Elegí la variante cuyo EXPLAIN muestre key=emailmsg_acct_date_idx y SIN 'Using filesort'.")
