/**
 * WebSocket client for real-time communication updates
 */

class CommunicationWebSocket {
    constructor(userId) {
        this.userId = userId;
        this.ws = null;
        this.reconnectInterval = 5000;
        this.connect();
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/communications/`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.onConnect();
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected. Reconnecting...');
            setTimeout(() => this.connect(), this.reconnectInterval);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    handleMessage(data) {
        switch(data.type) {
            case 'connection_established':
                console.log('Connection established:', data.message);
                break;
            
            case 'new_message':
                this.onNewMessage(data.message);
                break;
            
            case 'message_status_update':
                this.onMessageStatusUpdate(data.message_id, data.status);
                break;
            
            case 'conversation_assigned':
                this.onConversationAssigned(data.conversation);
                break;
            
            case 'typing_indicator':
                this.onTypingIndicator(data.user_id, data.username, data.is_typing);
                break;
        }
    }
    
    sendTypingIndicator(conversationId, isTyping) {
        this.send({
            type: 'typing',
            conversation_id: conversationId,
            is_typing: isTyping
        });
    }
    
    markMessageAsRead(messageId) {
        this.send({
            type: 'mark_read',
            message_id: messageId
        });
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }
    
    // Override these methods in your implementation
    onConnect() {}
    onNewMessage(message) {}
    onMessageStatusUpdate(messageId, status) {}
    onConversationAssigned(conversation) {}
    onTypingIndicator(userId, username, isTyping) {}
}
