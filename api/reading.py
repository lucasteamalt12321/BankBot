from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        html = '''<!DOCTYPE html>
<html>
<head><title>Тренажёр чтения</title></head>
<body>
<h1>🧸 Тренажёр чтения работает!</h1>
<p>Это тестовая версия</p>
</body>
</html>'''
        self.wfile.write(html.encode())
        return
