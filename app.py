import os
import psycopg2-binary
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, send_file
from flask import CORS

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    try:
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor,
            sslmode="require",
            connect_timeout=10 
        )
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
            code = str(course.get('course_code', '')).strip().upper()
            group = str(course.get('class_group', '')).strip().upper()
            
            query = """
                SELECT exam_id, course_code, course_title, class_group, exam_date, start_time, end_time, venue 
                FROM exam_timetable 
                WHERE UPPER(course_code) = %s AND UPPER(class_group) = %s
            """
            cursor.execute(query, (code, group))
            all_results.extend(cursor.fetchall())

        all_results.sort(key=lambda x: int(x['exam_id']) if x['exam_id'] is not None else 0)

        for res in all_results:
            for key, value in res.items():
                if hasattr(value, 'isoformat'):
                    res[key] = str(value)

        return jsonify({
            "status": "success",
            "count": len(all_results),
            "timetable": all_results
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/query', methods=['POST'])
def execute_query():
    data = request.get_json() or {}
    raw_query = data.get('query', '').strip()

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

@app.route('/api/check', methods=['POST'])
def check_course():
    data = request.json or {}
    code = str(data.get('course_code', '')).strip().upper()
    group = str(data.get('class_group', '')).strip().upper()

    connection = get_db_connection()
    if not connection:
        return jsonify({"status": "error", "message": "Database connection failed."}), 503
    
    try:
        cursor = connection.cursor()
        query = "SELECT 1 FROM exam_timetable WHERE UPPER(course_code) = %s AND UPPER(class_group) = %s LIMIT 1"
        cursor.execute(query, (code, group))
        exists = cursor.fetchone()
        
        if exists:
            return jsonify({"status": "exists"})
        else:
            return jsonify({"status": "missing", "message": f"Wait! {code} for {group} is not in the official timetable."})
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to verify course."}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/')
def home():
    return send_file('index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
