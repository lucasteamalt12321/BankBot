import sys, os
sys.path.insert(0, 'api')
os.environ['WEBHOOK_SECRET'] = 'test'
os.environ['BOT_TOKEN'] = 'test'
from index import app
app.run(port=5000, debug=False)
