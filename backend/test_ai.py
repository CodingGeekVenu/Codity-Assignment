import asyncio
from app.worker import generate_ai_failure_summary
import os

print('Generating AI Summary...')
summary = generate_ai_failure_summary('job-123', '{"data": "test payload"}', 'ZeroDivisionError: division by zero')
print('\n=== AI Summary Result ===\n')
print(summary)
print('\n=========================')
