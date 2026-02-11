"""
Intelligent conversation assignment system
Distributes conversations among available agents based on workload
"""

import logging
from django.contrib.auth.models import User
from django.db.models import Count, Q
from .models import Conversation, ConversationAssignment

logger = logging.getLogger(__name__)


def get_available_agents():
    """Get list of users who can be assigned conversations"""
    # Filter users who are staff (agents) and active
    # You can customize this based on your permission system
    return User.objects.filter(
        is_active=True,
        is_staff=True
    ).exclude(
        is_superuser=True  # Optionally exclude superusers from auto-assignment
    )


def get_agent_workload(agent):
    """Calculate current workload for an agent"""
    # Count active conversations assigned to this agent
    active_conversations = Conversation.objects.filter(
        assigned_to=agent,
        status__in=['open', 'assigned', 'pending']
    ).count()
    
    return active_conversations


def assign_conversation_to_agent(conversation, agent=None, assigned_by=None):
    """
    Assign a conversation to an agent
    If agent is None, automatically select the agent with lowest workload
    """
    if agent is None:
        # Auto-assign based on workload
        available_agents = get_available_agents()
        
        if not available_agents.exists():
            logger.warning("No available agents for assignment")
            conversation.status = 'pending'
            conversation.save()
            return None
        
        # Find agent with lowest workload
        agent_workloads = []
        for a in available_agents:
            workload = get_agent_workload(a)
            agent_workloads.append((a, workload))
        
        # Sort by workload and get agent with minimum
        agent_workloads.sort(key=lambda x: x[1])
        agent = agent_workloads[0][0]
        
        logger.info(f"Auto-assigning conversation {conversation.id} to {agent.username} (workload: {agent_workloads[0][1]})")
    
    # Assign the conversation
    conversation.assign_to(agent)
    
    if assigned_by:
        # Update the assignment record with who assigned it
        assignment = ConversationAssignment.objects.filter(
            conversation=conversation,
            is_active=True
        ).first()
        if assignment:
            assignment.assigned_by = assigned_by
            assignment.save()
    
    return agent


def reassign_conversation(conversation, new_agent, assigned_by):
    """Reassign a conversation to a different agent"""
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
    """Get all conversations that are not assigned to any agent"""
    return Conversation.objects.filter(
        Q(assigned_to__isnull=True) | Q(status='pending')
    ).order_by('-created_at')


def distribute_workload():
    """
    Redistribute unassigned conversations among agents
    This can be run periodically to balance workload
    """
    unassigned = get_unassigned_conversations()
    
    assigned_count = 0
    for conversation in unassigned:
        agent = assign_conversation_to_agent(conversation)
        if agent:
            assigned_count += 1
    
    logger.info(f"Distributed {assigned_count} conversations")
    return assigned_count
