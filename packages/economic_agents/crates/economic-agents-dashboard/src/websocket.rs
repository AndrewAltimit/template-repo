//! WebSocket handler for real-time updates.

use std::sync::Arc;

use axum::extract::State;
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::response::IntoResponse;
use futures::{SinkExt, StreamExt};
use tokio::select;
use tokio::sync::broadcast;
use tracing::{debug, error, info, warn};

use crate::models::{WsMessage, WsSubscription};
use crate::state::DashboardState;

/// WebSocket upgrade handler.
pub async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<DashboardState>>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_socket(socket, state))
}

/// Handle a WebSocket connection.
async fn handle_socket(socket: WebSocket, state: Arc<DashboardState>) {
    let (mut sender, mut receiver) = socket.split();

    // Subscribe to broadcasts
    let mut broadcast_rx = state.subscribe();

    // Track client connection
    state.add_ws_client().await;
    info!("WebSocket client connected");

    // Default subscription (all events and updates)
    let mut subscription = WsSubscription::default();

    // Spawn a task to forward broadcasts to the client
    let send_task = tokio::spawn(async move {
        loop {
            select! {
                // Receive broadcast messages
                msg = broadcast_rx.recv() => {
                    match msg {
                        Ok(ws_msg) => {
                            // Filter based on subscription
                            if should_send(&subscription, &ws_msg) {
                                let json = match serde_json::to_string(&ws_msg) {
                                    Ok(j) => j,
                                    Err(e) => {
                                        error!("Failed to serialize message: {}", e);
                                        continue;
                                    }
                                };

                                if sender.send(Message::Text(json)).await.is_err() {
                                    break;
                                }
                            }
                        }
                        Err(broadcast::error::RecvError::Lagged(n)) => {
                            warn!("WebSocket client lagged by {} messages", n);
                        }
                        Err(broadcast::error::RecvError::Closed) => {
                            break;
                        }
                    }
                }
            }
        }
    });

    // Handle incoming messages from the client
    while let Some(msg) = receiver.next().await {
        match msg {
            Ok(Message::Text(text)) => {
                // Try to parse as subscription update
                if let Ok(sub) = serde_json::from_str::<WsSubscription>(&text) {
                    subscription = sub;
                    debug!("Updated WebSocket subscription: {:?}", subscription);
                } else if let Ok(ws_msg) = serde_json::from_str::<WsMessage>(&text) {
                    // Handle ping
                    if matches!(ws_msg, WsMessage::Ping) {
                        let pong = serde_json::to_string(&WsMessage::Pong)
                            .expect("Pong enum serialization cannot fail");
                        // Note: can't send from here easily, client should handle ping/pong at ws level
                        debug!("Received ping, pong would be: {}", pong);
                    }
                } else {
                    debug!("Received unknown message: {}", text);
                }
            }
            Ok(Message::Ping(data)) => {
                debug!("Received WebSocket ping");
                // Pong is automatically sent by axum
                let _ = data; // satisfy unused warning
            }
            Ok(Message::Close(_)) => {
                info!("WebSocket client sent close");
                break;
            }
            Err(e) => {
                error!("WebSocket error: {}", e);
                break;
            }
            _ => {}
        }
    }

    // Cancel the send task
    send_task.abort();

    // Track client disconnection
    state.remove_ws_client().await;
    info!("WebSocket client disconnected");
}

/// Check if a message should be sent based on subscription.
fn should_send(subscription: &WsSubscription, message: &WsMessage) -> bool {
    match message {
        WsMessage::Event(_) => subscription.events,
        WsMessage::AgentUpdate(summary) => {
            if !subscription.agent_updates {
                return false;
            }
            if subscription.agent_ids.is_empty() {
                return true;
            }
            subscription.agent_ids.contains(&summary.id)
        }
        WsMessage::CycleCompleted { agent_id, .. } => {
            if !subscription.agent_updates {
                return false;
            }
            if subscription.agent_ids.is_empty() {
                return true;
            }
            subscription.agent_ids.contains(agent_id)
        }
        WsMessage::MetricsUpdate(_) => subscription.metrics,
        WsMessage::Error { .. } => true, // Always send errors
        WsMessage::Ping | WsMessage::Pong => true,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::EventSummary;
    use chrono::Utc;
    use uuid::Uuid;

    #[test]
    fn test_should_send_events() {
        let sub = WsSubscription {
            events: true,
            agent_updates: false,
            metrics: false,
            agent_ids: vec![],
        };

        let event = WsMessage::Event(EventSummary {
            id: Uuid::new_v4(),
            event_type: "test".to_string(),
            source: "test".to_string(),
            payload: serde_json::json!({}),
            timestamp: Utc::now(),
        });

        assert!(should_send(&sub, &event));
    }

    #[test]
    fn test_should_send_agent_filter() {
        let sub = WsSubscription {
            events: false,
            agent_updates: true,
            metrics: false,
            agent_ids: vec!["agent-1".to_string()],
        };

        let msg1 = WsMessage::CycleCompleted {
            agent_id: "agent-1".to_string(),
            cycle: 1,
            success: true,
        };

        let msg2 = WsMessage::CycleCompleted {
            agent_id: "agent-2".to_string(),
            cycle: 1,
            success: true,
        };

        assert!(should_send(&sub, &msg1));
        assert!(!should_send(&sub, &msg2));
    }

    #[test]
    fn test_errors_always_sent() {
        let sub = WsSubscription {
            events: false,
            agent_updates: false,
            metrics: false,
            agent_ids: vec![],
        };

        let error = WsMessage::Error {
            message: "test error".to_string(),
        };

        assert!(should_send(&sub, &error));
    }
}
