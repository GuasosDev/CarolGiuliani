"""
Intelligent conversation assignment system
Distributes conversations among available agents based on workload
"""

import logging
from django.contrib.auth.models import User
from .models import Conversation, ConversationAssignment

logger = logging.getLogger(__name__)


def get_available_agents(email_account):
    if email_account and email_account.user:
        return User.objects.filter(id=email_account.user_id)

    return User.objects.none()


def get_agent_workload(agent):
    """Calculate current workload for an agent"""
    # Count active conversations assigned to this agent
    active_conversations = Conversation.objects.filter(
        assigned_to=agent,
        status__in=['normal', 'pending']
    ).count()
    
    return active_conversations


def assign_conversation_to_agent(conversation, email_account=None, agent=None, assigned_by=None):
    """
    Asigna una conversación. Si ya tiene agente, NO reasigna
    (el hilo queda con quien lo generó / lo tiene).
    Para mover a otro usuario usar reassign_conversation (transferencia manual).
    """
    if conversation.assigned_to_id:
        logger.info(
            f"Conversation {conversation.id} already assigned to "
            f"{conversation.assigned_to.username}; skipping auto-assign"
        )
        return conversation.assigned_to

    if email_account is None:
        email_account = conversation.email_account

    if agent is None:
        available_agents = get_available_agents(email_account)

        if not available_agents.exists():
            logger.warning("No available agents for assignment")
            conversation.status = 'pending'
            conversation.save(update_fields=['status'])
            return None

        agent_workloads = []
        for a in available_agents:
            workload = get_agent_workload(a)
            agent_workloads.append((a, workload))

        agent_workloads.sort(key=lambda x: x[1])
        agent = agent_workloads[0][0]

        logger.info(
            f"Auto-assigning conversation {conversation.id} "
            f"to {agent.username} (workload: {agent_workloads[0][1]})"
        )

    conversation.assign_to(agent)

    if assigned_by:
        assignment = ConversationAssignment.objects.filter(
            conversation=conversation,
            is_active=True
        ).first()
        if assignment:
            assignment.assigned_by = assigned_by
            assignment.save(update_fields=['assigned_by'])

    return agent


def reassign_conversation(conversation, new_agent, assigned_by):
    """Reassign a conversation to a different agent (solo transferencia manual)."""
    # Deactivate current assignment
    current_assignments = ConversationAssignment.objects.filter(
        conversation=conversation,
        is_active=True
    )
    
    from django.utils import timezone
    for assignment in current_assignments:
        assignment.is_active = False
        assignment.unassigned_at = timezone.now()
        assignment.save()
    
    # Create new assignment
    conversation.assign_to(new_agent)
    
    # Update who assigned it
    new_assignment = ConversationAssignment.objects.filter(
        conversation=conversation,
        is_active=True
    ).first()
    if new_assignment:
        new_assignment.assigned_by = assigned_by
        new_assignment.save()
    
    logger.info(f"Reassigned conversation {conversation.id} to {new_agent.username} by {assigned_by.username}")
    
    return new_assignment


def get_agent_conversations(agent, status=None):
    """Get all conversations assigned to an agent"""
    queryset = Conversation.objects.filter(assigned_to=agent)
    
    if status:
        queryset = queryset.filter(status=status)
    
    return queryset.order_by('-updated_at')


def get_unassigned_conversations():
    """Solo conversaciones realmente sin agente (no reasignar pending ya asignados)."""
    return Conversation.objects.filter(
        assigned_to__isnull=True
    ).order_by('-created_at')


def distribute_workload():
    """
    Asigna conversaciones SIN agente. Nunca mueve hilos ya asignados.
    """
    unassigned = get_unassigned_conversations()

    assigned_count = 0
    for conversation in unassigned:
        agent = assign_conversation_to_agent(conversation)
        if agent:
            assigned_count += 1

    logger.info(f"Distributed {assigned_count} conversations")
    return assigned_count
