"""
Sistema de asignación de conversaciones.

Regla dura: si un hilo ya está asignado a una secretaria, NINGÚN camino
automático puede pasarlo a otra. Solo reassign_conversation (derivación manual).
"""

import logging
from django.contrib.auth.models import User
from django.db import transaction
from .models import Conversation, ConversationAssignment

logger = logging.getLogger(__name__)


def get_available_agents(email_account):
    """Dueño exclusivo (activo) de la casilla de email."""
    if email_account and email_account.user_id:
        return User.objects.filter(id=email_account.user_id, is_active=True)
    return User.objects.none()


def get_agent_workload(agent):
    """Carga actual de un agente (conversaciones activas)."""
    return Conversation.objects.filter(
        assigned_to=agent,
        status__in=['normal', 'pending']
    ).count()


@transaction.atomic
def assign_conversation_to_agent(conversation, email_account=None, agent=None, assigned_by=None):
    """
    Asigna solo si el hilo NO tiene agente.
    Si ya está asignado, lo deja como está (aunque se pase otro agent=).
    Para mover a otra persona: reassign_conversation.
    """
    if conversation is None or not getattr(conversation, 'pk', None):
        return None

    conversation = (
        Conversation.objects.select_for_update()
        .select_related('assigned_to', 'email_account')
        .get(pk=conversation.pk)
    )

    if conversation.assigned_to_id:
        if agent is not None and conversation.assigned_to_id != getattr(agent, 'id', agent):
            logger.warning(
                "Conversation %s already assigned to %s; refusing auto-assign to %s",
                conversation.id,
                conversation.assigned_to.username,
                getattr(agent, 'username', agent),
            )
        else:
            logger.info(
                "Conversation %s already assigned to %s; skipping auto-assign",
                conversation.id,
                conversation.assigned_to.username,
            )
        return conversation.assigned_to

    if email_account is None:
        email_account = conversation.email_account

    if agent is None:
        available_agents = get_available_agents(email_account)
        agent = available_agents.first()
        if not agent:
            logger.warning(
                "No owner agent for EmailAccount %s; conversation %s -> pending",
                getattr(email_account, 'id', None),
                conversation.id,
            )
            conversation.status = 'pending'
            conversation.save(update_fields=['status'])
            return None
        logger.info(
            "Auto-assigning conversation %s to %s (mailbox owner)",
            conversation.id,
            agent.username,
        )

    ok = conversation.assign_to(agent, allow_reassign=False, assigned_by=assigned_by)
    if not ok:
        conversation.refresh_from_db(fields=['assigned_to'])
        return conversation.assigned_to

    if assigned_by:
        assignment = ConversationAssignment.objects.filter(
            conversation=conversation,
            is_active=True,
        ).first()
        if assignment and assignment.assigned_by_id != assigned_by.id:
            assignment.assigned_by = assigned_by
            assignment.save(update_fields=['assigned_by'])

    return agent


@transaction.atomic
def reassign_conversation(conversation, new_agent, assigned_by):
    """
    Única vía para pasar un hilo de una secretaria a otra: derivación manual.
    """
    conversation = (
        Conversation.objects.select_for_update()
        .select_related('assigned_to')
        .get(pk=conversation.pk)
    )

    from django.utils import timezone

    current_assignments = ConversationAssignment.objects.filter(
        conversation=conversation,
        is_active=True,
    )
    for assignment in current_assignments:
        assignment.is_active = False
        assignment.unassigned_at = timezone.now()
        assignment.save(update_fields=['is_active', 'unassigned_at'])

    conversation.assign_to(new_agent, allow_reassign=True, assigned_by=assigned_by)

    new_assignment = ConversationAssignment.objects.filter(
        conversation=conversation,
        is_active=True,
    ).first()
    if new_assignment and assigned_by and new_assignment.assigned_by_id != assigned_by.id:
        new_assignment.assigned_by = assigned_by
        new_assignment.save(update_fields=['assigned_by'])

    logger.info(
        "Reassigned conversation %s to %s by %s (manual transfer)",
        conversation.id,
        new_agent.username,
        assigned_by.username if assigned_by else '?',
    )
    return new_assignment


def get_agent_conversations(agent, status=None):
    queryset = Conversation.objects.filter(assigned_to=agent)
    if status:
        queryset = queryset.filter(status=status)
    return queryset.order_by('-updated_at')


def get_unassigned_conversations():
    return Conversation.objects.filter(assigned_to__isnull=True).order_by('-created_at')


def distribute_workload():
    """Asigna solo conversaciones SIN agente. Nunca mueve hilos ya tomados."""
    unassigned = get_unassigned_conversations()
    assigned_count = 0
    for conversation in unassigned:
        agent = assign_conversation_to_agent(conversation)
        if agent:
            assigned_count += 1
    logger.info("Distributed %s conversations", assigned_count)
    return assigned_count
