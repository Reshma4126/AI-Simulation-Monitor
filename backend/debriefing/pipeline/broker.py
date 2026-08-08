"""
RabbitMQ Message Broker — CPR Debriefing System
=================================================
Thin wrapper around pika. Each pipeline stage publishes
completion events; the next stage consumes them.

Queue topology (one queue per stage transition):
  audio_ready      → triggers Whisper + Diarization
  transcript_ready → triggers Event Extractor
  events_ready     → triggers ACLS FSM
  findings_ready   → triggers Scoring Engine
  scores_ready     → triggers OpenAI Narrative + PDF
  report_ready     → final delivery notification

Each message is a JSON envelope:
  { "session_id": str, "payload": dict, "timestamp": float }

Author: Deva
"""

from __future__ import annotations
import json
import logging
import time
from typing import Callable, Optional
import pika

logger = logging.getLogger(__name__)

QUEUES = [
    "audio_ready",
    "transcript_ready",
    "events_ready",
    "findings_ready",
    "scores_ready",
    "report_ready",
]


class Broker:
    """
    Manages RabbitMQ connection, queue declaration, publish, and consume.
    Designed for single-threaded use per worker process.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
    ):
        self.host = host
        self.port = port
        self.credentials = pika.PlainCredentials(username, password)
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[pika.channel.Channel] = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self):
        params = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=self.credentials,
            heartbeat=600,
            blocked_connection_timeout=300,
        )
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        self._declare_queues()
        logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")

    def disconnect(self):
        if self._connection and not self._connection.is_closed:
            self._connection.close()
            logger.info("Disconnected from RabbitMQ")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    # ------------------------------------------------------------------
    # Publish / Consume
    # ------------------------------------------------------------------

    def publish(self, queue: str, session_id: str, payload: dict):
        """Publish a message to a queue."""
        message = json.dumps({
            "session_id": session_id,
            "payload": payload,
            "timestamp": time.time(),
        })
        self._channel.basic_publish(
            exchange="",
            routing_key=queue,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,   # persistent — survives broker restart
                content_type="application/json",
            ),
        )
        logger.info(f"Published → [{queue}] session={session_id}")

    def consume(self, queue: str, handler: Callable[[str, dict], None]):
        """
        Block and consume messages from a queue.
        handler(session_id, payload) is called for each message.
        Acks on success, nacks (requeue=False) on unhandled exception.
        """
        def _callback(ch, method, properties, body):
            try:
                msg = json.loads(body)
                handler(msg["session_id"], msg["payload"])
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info(f"Processed ← [{queue}] session={msg['session_id']}")
            except Exception as e:
                logger.error(f"Handler error on [{queue}]: {e}", exc_info=True)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        self._channel.basic_qos(prefetch_count=1)
        self._channel.basic_consume(queue=queue, on_message_callback=_callback)
        logger.info(f"Consuming from [{queue}] — waiting for messages...")
        self._channel.start_consuming()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _declare_queues(self):
        for q in QUEUES:
            self._channel.queue_declare(queue=q, durable=True)
        logger.debug(f"Declared queues: {QUEUES}")
