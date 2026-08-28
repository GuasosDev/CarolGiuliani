"""
Intelligent conversation assignment system
Asigna conversaciones de forma EXCLUSIVA al usuario dueño de la cuenta de email.
"""

import logging
from django.contrib.auth.models import User
from django.db import transaction
from .models import Conversation, ConversationAssignment

logger = logging.getLogger(__name__)


def get_available_agents(email_account):
    """
    Retorna EXCLUSIVAMENTE al usuario dueño de la cuenta de email.
    """
    if email_account and email_account.user:
        return User.objects.filter(id=email_account.user_id, is_active=True)

    return User.objects.none()


def assign_conversation_to_agent(conversation, email_account=None, agent=None, assigned_by=None):
    """
    Asigna la conversación exclusivamente al dueño del email.
    Si ya tiene agente asignado, NO se reasigna.
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
                f"No owner agent found for EmailAccount {getattr(email_account, 'id', None)}. "
                f"Conversation {conversation.id} set to pending."
            )
            conversation.status = 'pending'
            conversation.save(update_fields=['status'])
            return None

    conversation.assign_to(agent)
    logger.info(
        f"Assigned conversation {conversation.id} exclusively to "
        f"{agent.username} (Account: {email_account})"
    )

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
    """Reassign a conversation to a different agent (solo transferencia manual)."""
    current_assignments = ConversationAssignment.objects.filter(
        conversation=conversation,
        is_active=True,
    )

    from django.utils import timezone
    for assignment in current_assignments:
        assignment.is_active = False
        assignment.unassigned_at = timezone.now()
        assignment.save()

    conversation.assign_to(new_agent)

    new_assignment = ConversationAssignment.objects.filter(
        conversation=conversation,
        is_active=True,
    ).first()
    if new_assignment and assigned_by and new_assignment.assigned_by_id != assigned_by.id:
        new_assignment.assigned_by = assigned_by
        new_assignment.save()

    logger.info(f"Reassigned conversation {conversation.id} to {new_agent.username} by {assigned_by.username}")

    return new_assignment


def get_agent_conversations(agent, status=None):
    """Obtiene todas las conversaciones asignadas a un agente especifico."""
    queryset = Conversation.objects.filter(assigned_to=agent)

    if status:
        queryset = queryset.filter(status=status)

    return queryset.order_by('-updated_at')


def get_unassigned_conversations():
    """Solo conversaciones realmente sin agente."""
    return Conversation.objects.filter(
        assigned_to__isnull=True
    ).order_by('-created_at')


def distribute_workload():
    """
    Asigna conversaciones SIN agente a su dueño exclusivo de email.
    """
    unassigned = get_unassigned_conversations()
    assigned_count = 0
    for conversation in unassigned:
        agent = assign_conversation_to_agent(conversation)
        if agent:
            assigned_count += 1

    logger.info(f"Distributed {assigned_count} conversations")
    return assigned_count
