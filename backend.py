import mysql.connector
from mysql.connector import Error
import google.generativeai as genai
import json
import os
import re
import logging

# Set up logging
logging.basicConfig(filename='backend.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

class DBAssistantBackend:
    def __init__(self):
        self.connected = False
        self.cnx = None
        self.cursor = None
        self.messages = []
        self.schema_info = ""
        self.system_prompt = """You are a MySQL database assistant. The user will give you natural language instructions to manipulate the database.
Use the following database schema to generate accurate SQL queries: {schema}
Generate the SQL query and enclose it in [SQL] and [/SQL]. Support all types of SQL queries, including but not limited to:
- SELECT (with joins, subqueries, aggregations, window functions, etc.)
- INSERT, UPDATE, DELETE (always include WHERE clauses for UPDATE/DELETE to avoid unintended data loss unless explicitly requested)
- CREATE, ALTER, DROP for tables, indexes, views, procedures, etc.
- SHOW, DESCRIBE for metadata queries
- Transactions (BEGIN, COMMIT, ROLLBACK if needed)
- Any other valid MySQL statements
If the query is potentially destructive (e.g., DROP, DELETE without WHERE), add a note in your response warning the user.
Do not include execution code. I will handle execution and return results.
Respond conversationally, explaining the action briefly before providing the SQL.
For large result sets in SELECT, consider adding LIMIT unless the user specifies otherwise."""
        self.messages.append({"role": "system", "content": self.system_prompt})
        
        # Configure Gemini and connect to database
        self.configure_gemini()
        self.connect_to_database()

    def configure_gemini(self):
        """Load Gemini API key from db_credentials.json and configure the model."""
        credentials_file = "db_credentials.json"
        try:
            if not os.path.exists(credentials_file):
                logging.warning(f"Credentials file '{credentials_file}' not found.")
                return False
            
            with open(credentials_file, 'r') as f:
                credentials = json.load(f)
            
            if 'api_key' not in credentials:
                logging.warning("Gemini API key missing in db_credentials.json.")
                return False
            
            genai.configure(api_key=credentials['api_key'])
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            logging.info("Gemini API configured successfully.")
            return True
        except json.JSONDecodeError:
            logging.error("Invalid JSON format in db_credentials.json.")
            return False
        except Exception as e:
            logging.error(f"Failed to configure Gemini: {e}")
            return False

    def connect_to_database(self):
        credentials_file = "db_credentials.json"
        try:
            if not os.path.exists(credentials_file):
                return f"AI: Error: '{credentials_file}' not found. Please create a JSON file with host, user, password, database, and api_key."
            
            with open(credentials_file, 'r') as f:
                credentials = json.load(f)
            
            required_keys = {'host', 'user', 'password', 'database'}
            if not required_keys.issubset(credentials.keys()):
                return "AI: Invalid JSON format. Please include host, user, password, and database in db_credentials.json."
            
            self.cnx = mysql.connector.connect(
                host=credentials['host'],
                user=credentials['user'],
                password=credentials['password'],
                database=credentials['database'],
                autocommit=False  # Explicitly set autocommit to False for transaction control
            )
            self.cursor = self.cnx.cursor()
            self.connected = True
            
            # Fetch schema information
            self.schema_info = self._get_schema_info()
            self.system_prompt = self.system_prompt.format(schema=self.schema_info)
            self.messages[0]["content"] = self.system_prompt  # Update system prompt with schema
            
            logging.info("Connected to database and fetched schema.")
            return "AI: Connected to MySQL database successfully. Schema loaded. What would you like to do with the database?"
        except Error as e:
            logging.error(f"Connection failed: {e}")
            return f"AI: Connection failed: {e}\nPlease check your credentials in '{credentials_file}' and try again."
        except json.JSONDecodeError:
            logging.error("Invalid JSON format in db_credentials.json.")
            return f"AI: Error: Invalid JSON format in '{credentials_file}'. Please fix the file."

    def _get_schema_info(self):
        """Fetch database schema: tables and their columns."""
        try:
            self.cursor.execute("SHOW TABLES")
            tables = self.cursor.fetchall()
            schema_str = "Database Schema:\n"
            for table in tables:
                table_name = table[0]
                schema_str += f"Table: {table_name}\n"
                self.cursor.execute(f"DESCRIBE {table_name}")
                columns = self.cursor.fetchall()
                for col in columns:
                    schema_str += f"- {col[0]}: {col[1]} ({', '.join([flag for flag in col[2:] if flag])})\n"
                schema_str += "\n"
            return schema_str.strip()
        except Error as e:
            logging.error(f"Failed to fetch schema: {e}")
            return "Schema unavailable due to error."

    def get_connection_status(self):
        return self.connect_to_database()

    def process_message(self, user_input):
        if not self.connected:
            return "AI: Please ensure database connection is established before sending commands.", ""
        
        if not hasattr(self, 'model'):
            return "AI: Gemini API not configured. Please check your 'api_key' in db_credentials.json.", ""
        
        self.messages.append({"role": "user", "content": user_input})
        try:
            # Simulate chat by passing the full message history
            formatted_messages = []
            for msg in self.messages:
                role = "user" if msg["role"] == "user" else "model"
                formatted_messages.append(f"{role}: {msg['content']}")
            full_prompt = "\n".join(formatted_messages)
            
            response = self.model.generate_content(full_prompt)
            response_text = response.text
            logging.info(f"Gemini response: {response_text}")
        except Exception as e:
            logging.error(f"Error communicating with Gemini model: {e}")
            return f"AI: Error communicating with AI model: {e}", ""
        
        # Extract SQL from response
        sql_match = re.search(r'\[SQL\](.*?)\[/SQL\]', response_text, re.DOTALL)
        execution_result = ""
        if sql_match:
            sql = sql_match.group(1).strip()
            logging.info(f"Generated SQL: {sql}")
            try:
                # Execute in a transaction for atomicity
                statements = [s.strip() for s in re.split(r';(?!\s*\))', sql) if s.strip()]  # Split on ';' not inside parentheses
                results = []
                for stmt in statements:
                    self.cursor.execute(stmt)
                    if stmt.lower().startswith(('select', 'show', 'describe', 'explain')):
                        rows = self.cursor.fetchall()
                        if rows:
                            # Truncate large results for display (full results logged if needed)
                            display_rows = rows[:100]  # Limit to 100 rows
                            results.append("Results (showing first 100 rows):\n" + "\n".join(str(row) for row in display_rows))
                            if len(rows) > 100:
                                results.append(f"\n... (truncated; total rows: {len(rows)})")
                        else:
                            results.append("No results found.")
                    else:
                        results.append("Statement executed.")
                
                self.cnx.commit()  # Commit only if all statements succeed
                execution_result = "\n".join(results)
            except Error as e:
                self.cnx.rollback()  # Rollback on error
                logging.error(f"Execution failed: {e}")
                execution_result = f"Execution failed: {e}"
            
            # Remove SQL tags from response
            response_text = re.sub(r'\[SQL\].*?\[/SQL\]', '', response_text).strip()
            if execution_result:
                response_text += f"\n{execution_result}"
        
        self.messages.append({"role": "assistant", "content": response_text})
        return response_text, execution_result