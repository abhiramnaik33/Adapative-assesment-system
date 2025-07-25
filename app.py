from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import google.generativeai as genai
from sentence_transformers import SentenceTransformer, util
from datetime import datetime
import json  # Ensure this import is present for JSON parsing

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///questions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Neo4j configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your_password")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# SentenceTransformer model
similarity_model = SentenceTransformer('all-MiniLM-L6-v2')

# Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Question model
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)
    bloom = db.Column(db.String(20), nullable=False)
    tags = db.Column(db.String(100))
    validation_feedback = db.Column(db.Text)
    similarity_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Question Paper Requirements model
class QuestionPaper(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requirements = db.Column(db.Text, nullable=False)  
    tags = db.Column(db.String(100))  
    bloom_levels = db.Column(db.String(100))  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    generated_paper = db.Column(db.Text)  

# Test Neo4j connection
def test_neo4j_connection():
    try:
        with driver.session() as session:
            result = session.run("RETURN 1")
            return result.single()[0] == 1
    except Exception as e:
        print(f"Neo4j connection error: {e}")
        return False

@app.route('/test_neo4j')
def test_neo4j():
    if test_neo4j_connection():
        return jsonify({"status": "Neo4j connected successfully"})
    return jsonify({"status": "Neo4j connection failed"}), 500

# Fetch topic graph for selection
@app.route('/topic_graph')
def topic_graph():
    def fetch_bok_ka_ku(tx):
        result = tx.run("""
            MATCH (bok:BoK)<-[:Belongs_to]-(ka:KA)<-[:Unit_Of]-(ku)
            WHERE any(lbl IN labels(ku) WHERE lbl STARTS WITH 'KU')
            RETURN bok.shortName AS bok, ka.shortName AS ka, ku.shortName AS ku_short, ku.fullName AS ku_full
        """)
        node_map = {}
        edges = []

        for record in result:
            bok, ka, ku_short, ku_full = record["bok"], record["ka"], record["ku_short"], record["ku_full"]
            node_map[bok] = {"id": bok, "label": bok}
            node_map[ka] = {"id": ka, "label": ka}
            node_map[ku_short] = {"id": ku_short, "label": ku_short, "fullName": ku_full}
            edges.append({"source": bok, "target": ka, "relationship": "HAS_KA"})
            edges.append({"source": ka, "target": ku_short, "relationship": "HAS_KU"})

        # Fallback to old topic structure if BoK-KA-KU is empty
        if not node_map:
            result = tx.run("""
            MATCH (t:Topic)-[r:HAS_SUBTOPIC|RELATED_TO]->(t2:Topic)
            RETURN t.name AS source, type(r) AS relationship, t2.name AS target
            """)
            edges = [{"source": r["source"], "relationship": r["relationship"], "target": r["target"]} for r in result]
            nodes = tx.run("MATCH (t:Topic) RETURN t.name AS name").value()
            return {"nodes": [{"id": name, "label": name} for name in nodes], "edges": edges}

        return {"nodes": list(node_map.values()), "edges": edges}

    try:
        with driver.session() as session:
            graph = session.read_transaction(fetch_bok_ka_ku)
        return jsonify(graph)
    except Exception as e:
        return jsonify({"error": f"Neo4j error: {str(e)}"}), 500

# Compute similarity score
def compute_similarity(new_question_text):
    existing_questions = Question.query.all()
    existing_texts = [q.text for q in existing_questions]
    if not existing_texts:
        return 0.0
    new_embedding = similarity_model.encode(new_question_text, convert_to_tensor=True)
    existing_embeddings = similarity_model.encode(existing_texts, convert_to_tensor=True)
    cosine_scores = util.cos_sim(new_embedding, existing_embeddings)
    return float(cosine_scores.max())

# Gemini difficulty validation
def validate_difficulty_gemini(question_text, claimed_difficulty):
    try:
        prompt = f"""
        You are an exam question reviewer. Given a descriptive question and its claimed difficulty level (Easy, Medium, or Hard), respond with only one of the following:
        1. Claimed difficulty matched
        2. Claimed difficulty not matched
        Question: "{question_text}"
        Claimed Difficulty: {claimed_difficulty}
        Your answer:
        """
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API failed: {e}")
        return "Gemini validation failed"

# Home route
@app.route('/')
def home():
    return render_template('home.html')

# Submission form (GET)
@app.route('/submit', methods=['GET'])
def show_form():
    return render_template('submit_question.html')

# Submit question
@app.route('/submit', methods=['POST'])
def submit_question():
    question_text = request.form.get('question_text')
    difficulty = request.form.get('difficulty')
    bloom_level = request.form.get('bloom_level')
    topics = request.form.get('topics', '').split(',')

    if not question_text or not difficulty or not bloom_level or topics == ['']:
        return render_template('submit_question.html', error="All fields are required"), 400

    # Compute similarity
    similarity = compute_similarity(question_text)

    # Validate with Gemini
    validation_feedback = validate_difficulty_gemini(question_text, difficulty)

    # Save to SQLite
    new_question = Question(
        text=question_text,
        difficulty=difficulty,
        bloom=bloom_level,
        tags=','.join(topics),
        validation_feedback=validation_feedback,
        similarity_score=similarity
    )
    db.session.add(new_question)
    db.session.commit()

    # Save to Neo4j
    def create_question(tx, q_id, text, ku_names):
        tx.run("""
        CREATE (q:Question {id: $q_id, text: $text})
        WITH q
        UNWIND $ku_names AS ku_name
        MATCH (ku) WHERE any(lbl IN labels(ku) WHERE lbl STARTS WITH 'KU') AND ku.shortName = ku_name
        CREATE (q)-[:BELONGS_TO]->(ku)
        """, q_id=q_id, text=text, ku_names=ku_names)

    try:
        with driver.session() as session:
            session.write_transaction(create_question, new_question.id, question_text, topics)
    except Exception as e:
        db.session.rollback()
        return render_template('submit_question.html', error=f"Neo4j error: {str(e)}"), 500

    return render_template(
        'submit_question.html',
        success=True,
        similarity=round(similarity, 2),
        feedback=validation_feedback
    )

# Show all questions
@app.route('/questions')
def show_questions():
    all_questions = Question.query.all()
    return render_template('view_questions.html', questions=all_questions)



# Show all question papers
@app.route('/question_papers')
def show_question_papers():
    question_papers = QuestionPaper.query.order_by(QuestionPaper.created_at.desc()).all()
    question_paper_details = []
    for paper in question_papers:
        question_ids = json.loads(paper.generated_paper) if paper.generated_paper else []
        paper_questions = Question.query.filter(Question.id.in_(question_ids)).all()
        question_paper_details.append({
            "paper": paper,
            "questions": paper_questions
        })
    return render_template('question_papers.html', question_papers=question_paper_details)

# Delete question paper (add this right after the above route)
@app.route('/delete_paper/<int:id>')
def delete_paper(id):
    paper = QuestionPaper.query.get_or_404(id)
    try:
        db.session.delete(paper)
        db.session.commit()
        return redirect(url_for('show_question_papers'))
    except Exception as e:
        db.session.rollback()
        return f"Error deleting paper: {str(e)}", 500


    
# Submit question paper requirements (GET for form, POST for submission)
@app.route('/generate_paper', methods=['GET', 'POST'])
def generate_paper():
    if request.method == 'POST':
        difficulty_distribution = {
            "Easy": int(request.form.get('easy', 0)),
            "Medium": int(request.form.get('medium', 0)),
            "Hard": int(request.form.get('hard', 0))
        }
        tags = request.form.get('tags', '').split(',')
        bloom_levels = request.form.get('bloom_levels', '').split(',')

        # Validate that at least one question is requested
        if sum(difficulty_distribution.values()) == 0:
            return render_template('generate_paper.html', error="At least one question is required"), 400

        # Store requirements in the database
        requirements_json = jsonify(difficulty_distribution).get_data(as_text=True)
        new_paper = QuestionPaper(
            requirements=requirements_json,
            tags=','.join(tags),
            bloom_levels=','.join(bloom_levels)
        )
        db.session.add(new_paper)
        db.session.commit()

        # Fetch matching questions
        questions = fetch_matching_questions(difficulty_distribution, tags, bloom_levels)

        # Store the generated paper (list of question IDs)
        question_ids = [q.id for q in questions]
        new_paper.generated_paper = jsonify(question_ids).get_data(as_text=True)
        db.session.commit()

        return render_template('view_paper.html', questions=questions, paper_id=new_paper.id)

    return render_template('generate_paper.html')
    
# Fetch matching questions based on requirements
def fetch_matching_questions(difficulty_distribution, tags, bloom_levels):
    selected_questions = []
    
    # Filter questions for each difficulty level
    for difficulty, count in difficulty_distribution.items():
        if count == 0:
            continue
        query = Question.query.filter(Question.difficulty == difficulty)
        
        # Filter by tags if provided
        if tags and tags != ['']:
            query = query.filter(Question.tags.in_(tags))
        
        # Filter by Bloom levels if provided
        if bloom_levels and bloom_levels != ['']:
            query = query.filter(Question.bloom.in_(bloom_levels))
        
        # Fetch the required number of questions
        questions = query.limit(count).all()
        selected_questions.extend(questions)
    
    return selected_questions
# Admin panel
@app.route('/admin', methods=['GET'])
def admin_panel():
    bloom = request.args.get('bloom')
    difficulty = request.args.get('difficulty')
    tag = request.args.get('tag')
    sort_by = request.args.get('sort', 'created_at')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Question.query
    if bloom:
        query = query.filter(Question.bloom == bloom)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    if tag:
        query = query.filter(Question.tags.like(f"%{tag}%"))
    if sort_by == "similarity":
        query = query.order_by(Question.similarity_score.desc())
    else:
        query = query.order_by(Question.created_at.desc())

    try:
        pagination = query.paginate(page=page, per_page=per_page)
        questions = pagination.items
    except Exception as e:
        return render_template('admin_panel.html', error=f"Database error: {str(e)}"), 500

    return render_template('admin_panel.html', questions=questions, pagination=pagination)

# Edit question
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_question(id):
    question = Question.query.get_or_404(id)
    if request.method == 'POST':
        question.text = request.form.get('question_text')
        question.difficulty = request.form.get('difficulty')
        question.bloom = request.form.get('bloom_level')
        question.tags = request.form.get('tags')
        try:
            db.session.commit()
            return "Question updated successfully!"
        except Exception as e:
            db.session.rollback()
            return f"Error updating question: {str(e)}", 500
    return render_template('edit_question.html', question=question)

# Delete question
@app.route('/delete/<int:id>')
def delete_question(id):
    question = Question.query.get_or_404(id)
    try:
        db.session.delete(question)
        db.session.commit()
        return "Question deleted successfully!"
    except Exception as e:
        db.session.rollback()
        return f"Error deleting question: {str(e)}", 500

# Check similarity
@app.route('/check_similarity', methods=['POST'])
def check_similarity():
    question_text = request.json.get('question_text')
    if not question_text:
        return jsonify({"error": "Question text is required"}), 400
    score = compute_similarity(question_text)
    return jsonify({"similarity_score": round(score, 2)})

# Serve topics.json
@app.route("/static/topics.json")
def get_topics_file():
    try:
        return send_from_directory('static', 'topics.json')
    except Exception as e:
        return jsonify({"error": f"File error: {str(e)}"}), 404

# Run the app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
