"""
TradeIQ IPC Handler - Processes requests via stdin/stdout instead of HTTP
This replaces the Flask HTTP server for native desktop app communication
"""

import sys
import json
import os
from io import BytesIO, StringIO
from flask import Flask, request as flask_request
from werkzeug.wrappers import Request, Response
from werkzeug.serving import WSGIRequestHandler

# Import the main app module
import app as tradeiq_app

# Get the Flask app instance
app = tradeiq_app.app

def process_request(request_data):
    """Process a request and return response"""
    try:
        # Parse request
        method = request_data.get('method', 'GET')
        path = request_data.get('path', '/')
        body = request_data.get('body')
        headers = request_data.get('headers', {})
        
        # Debug logging for signal requests
        if '/api/signals/receive' in path:
            print(f"[IPC process_request] Method: {method}, Path: {path}", file=sys.stderr)
            print(f"[IPC process_request] Body type: {type(body)}, Body: {body}", file=sys.stderr)
            print(f"[IPC process_request] Headers: {headers}", file=sys.stderr)
            sys.stderr.flush()
        
        # Convert body to JSON bytes if it's a dict/list
        body_bytes = b''
        if body:
            if isinstance(body, (dict, list)):
                body_str = json.dumps(body)
            else:
                body_str = str(body)
            body_bytes = body_str.encode('utf-8')
        
        # Create a seekable BytesIO for wsgi.input (Flask may read it multiple times)
        wsgi_input = BytesIO(body_bytes)
        
        # Parse query string from path if present
        path_only = path
        query_string = ''
        if '?' in path:
            path_only, query_string = path.split('?', 1)
        
        # Create a Werkzeug request object
        environ = {
            'REQUEST_METHOD': method,
            'PATH_INFO': path_only,
            'QUERY_STRING': query_string,
            'CONTENT_TYPE': headers.get('Content-Type', 'application/json'),
            'CONTENT_LENGTH': str(len(body_bytes)),
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'wsgi.input': wsgi_input,
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '0',
            'HTTP_HOST': 'localhost',
        }
        
        # Add headers to environ
        for key, value in headers.items():
            env_key = 'HTTP_' + key.upper().replace('-', '_')
            environ[env_key] = value
        
        # Process with Flask app
        with app.request_context(environ):
            response = app.full_dispatch_request()
            
            # Get response data
            response_data = b''.join(response.response).decode('utf-8')
            
            # Try to parse as JSON
            try:
                response_json = json.loads(response_data)
            except:
                response_json = {'html': response_data}
            
            return {
                'status': response.status_code,
                'headers': dict(response.headers),
                'data': response_json
            }
            
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        print(f"[IPC Error] {error_msg}", file=sys.stderr)
        print(f"[IPC Traceback] {traceback_str}", file=sys.stderr)
        return {
            'status': 500,
            'headers': {'Content-Type': 'application/json'},
            'data': {
                'error': error_msg,
                'traceback': traceback_str
            }
        }

def reload_config():
    """Reload configuration from .env file"""
    import importlib
    from dotenv import load_dotenv
    
    # Reload .env file
    env_path = tradeiq_app.env_file_path
    load_dotenv(dotenv_path=env_path, override=True)
    
    # Reload config values in the app module
    tradeiq_app.openai_api_key = os.getenv('OPENAI_API_KEY')
    tradeiq_app.execution_model = os.getenv('EXECUTION_MODEL', 'gpt-4-turbo-preview')
    tradeiq_app.builder_model = os.getenv('BUILDER_MODEL', 'gpt-4-turbo-preview')
    
    # Reinitialize AI components if API key is available
    if tradeiq_app.openai_api_key:
        from prompt_builder import PromptBuilder
        from signal_processor import SignalProcessor
        tradeiq_app.prompt_builder = PromptBuilder(api_key=tradeiq_app.openai_api_key, model=tradeiq_app.builder_model)
        tradeiq_app.signal_processor = SignalProcessor(api_key=tradeiq_app.openai_api_key, model=tradeiq_app.execution_model)
    
    print("✓ Configuration reloaded from .env", file=sys.stderr)

def main():
    """Main IPC loop - read from stdin, write to stdout"""
    print("🚀 TradeIQ IPC Handler starting...", file=sys.stderr)
    
    # Initialize database
    tradeiq_app.db.init_db()
    print("✓ Database initialized", file=sys.stderr)
    
    # Reload config to ensure latest values
    reload_config()
    
    # Signal that we're ready (this will be read by IPC bridge)
    print("📡 Ready to receive requests via stdin", file=sys.stderr)
    sys.stderr.flush()  # Ensure message is sent immediately
    
    # Read line by line from stdin
    for line in sys.stdin:
        try:
            # Parse request
            request_data = json.loads(line.strip())
            request_id = request_data.get('id')
            path = request_data.get('path', '')
            
            # Log incoming requests for debugging
            if '/api/signals/receive' in path:
                print(f"[IPC] 📥 Received signal request: {path}", file=sys.stderr)
                print(f"[IPC] Request body: {json.dumps(request_data.get('body', {}), indent=2)}", file=sys.stderr)
                sys.stderr.flush()
            
            # Process request
            response = process_request(request_data)
            
            # Log response for debugging
            if '/api/signals/receive' in path:
                print(f"[IPC] 📤 Sending response: status={response.get('status')}", file=sys.stderr)
                if response.get('data'):
                    print(f"[IPC] Response data: {json.dumps(response.get('data'), indent=2)[:500]}", file=sys.stderr)
                sys.stderr.flush()
            
            # Send response
            response_json = json.dumps({
                'id': request_id,
                'data': response
            })
            
            print(response_json)
            sys.stdout.flush()
            
        except json.JSONDecodeError as e:
            error_response = json.dumps({
                'id': request_data.get('id') if 'request_data' in locals() else None,
                'error': f'Invalid JSON: {str(e)}'
            })
            print(error_response)
            sys.stdout.flush()
            
        except Exception as e:
            import traceback
            error_msg = str(e)
            error_traceback = traceback.format_exc()
            print(f"[IPC] ❌ Error processing request: {error_msg}", file=sys.stderr)
            print(f"[IPC] Traceback: {error_traceback}", file=sys.stderr)
            sys.stderr.flush()
            
            error_response = json.dumps({
                'id': request_data.get('id') if 'request_data' in locals() else None,
                'error': error_msg,
                'traceback': error_traceback
            })
            print(error_response)
            sys.stdout.flush()

if __name__ == '__main__':
    main()

