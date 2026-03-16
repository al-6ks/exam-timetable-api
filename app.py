import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
# Allows your frontend to communicate with this backend
CORS(app)

# YOUR NEON CONNECTION STRING
DATABASE_URL = "postgresql://neondb_owner:npg_JPhUIp3gA4CD@ep-shiny-queen-alvsna5p.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_db_connection():
    try:
        # RealDictCursor makes the results behave like a Python dictionary (key: value)
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Database Connection Error: {e}")
        return None

@app.route('/api/timetable', methods=['POST'])
def build_timetable():
    data = request.json or {}
    courses_to_fetch = data.get('courses', [])

    if not courses_to_fetch:
        return jsonify({"status": "info", "message": "No courses provided."}), 200

    connection = get_db_connection()
    if not connection:
        return jsonify({"status": "error", "message": "Database connection failed."}), 503
    
    try:
        cursor = connection.cursor()
        all_results = []
        
        for course in courses_to_fetch:
            # Clean inputs
            code = str(course.get('course_code', '')).strip().upper()
            group = str(course.get('class_group', '')).strip().upper()
            
            # PostgreSQL query
            query = """
                SELECT exam_id, course_code, course_title, class_group, exam_date, start_time, end_time, venue 
                FROM exam_timetable 
                WHERE UPPER(course_code) = %s AND UPPER(class_group) = %s
            """
            cursor.execute(query, (code, group))
            all_results.extend(cursor.fetchall())

        # Sort by exam_id (handling cases where id might be string or int)
        all_results.sort(key=lambda x: int(x['exam_id']) if x['exam_id'] is not None else 0)

        # Convert date and time objects to strings so JSON can handle them
        for res in all_results:
            for key, value in res.items():
                if hasattr(value, 'isoformat'): # Handles Date, Time, and Datetime objects
                    res[key] = str(value)

        return jsonify({
            "status": "success",
            "count": len(all_results),
            "timetable": all_results
        })
    except Exception as e:
        print(f"Query Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/query', methods=['POST'])
def execute_query():
    data = request.get_json() or {}
    raw_query = data.get('query', '').strip()

    # Simple logic to add ordering if missing
    if "FROM exam_timetable" in raw_query.lower() and "order by" not in raw_query.lower():
        raw_query = "SELECT * FROM exam_timetable ORDER BY exam_id ASC"

    connection = get_db_connection()
    if not connection: 
        return jsonify({"status": "error", "message": "DB error"}), 503
        
    try:
        cursor = connection.cursor()
        cursor.execute(raw_query)
        
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        
        # THE FIX: Added .values() here. Instead of reading the keys (exam_id), 
        # it now reads the actual values inside the row!
        json_rows = [[str(item) if item is not None else None for item in row.values()] for row in rows]

        return jsonify({
            "status": "success",
            "columns": columns,
            "data": json_rows
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    # Use environment port for deployment, default to 5000 for local testing
    port = int(os.environ.get("PORT", 5000))
    print(f"Backend running on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)