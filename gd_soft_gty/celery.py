"""
Celery configuration for gd_soft_gty project.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gd_soft_gty.settings')

app = Celery('gd_soft_gty')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Periodic tasks configuration
app.conf.beat_schedule = {
    'sync-emails-every-5-minutes': {
        'task': 'communications.tasks.sync_all_email_accounts',
        'schedule': crontab(minute='*/5'),
    },
    'process-email-queue-every-minute': {
        'task': 'communications.tasks.process_email_queue',
        'schedule': crontab(minute='*'),
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
