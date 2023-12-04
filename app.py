import os
from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from nltk.stem import PorterStemmer
from nltk.stem import WordNetLemmatizer
from rake_nltk import Rake
from language_tool_python import LanguageTool
import pandas as pd
tool = LanguageTool('en-US')
rake_nltk_var = Rake()
from flask import send_from_directory



app = Flask(__name__)
app.config['SECRET_KEY'] = 'abcd123'  


TEACHER_UPLOAD_FOLDER = 'teacher_upload'
STUDENT_UPLOAD_FOLDER = 'stu_upload'
QUESTION_FOLDER = 'questions'
QUESTIONS_FOLDER = os.path.join(TEACHER_UPLOAD_FOLDER, QUESTION_FOLDER)
app.config['QUESTIONS_FOLDER'] = QUESTIONS_FOLDER
app.config['TEACHER_UPLOAD_FOLDER'] = TEACHER_UPLOAD_FOLDER
app.config['STUDENT_UPLOAD_FOLDER'] = STUDENT_UPLOAD_FOLDER
QUESTIONS_FOLDER = os.path.join(TEACHER_UPLOAD_FOLDER, 'questions')
ANSWERS_FOLDER = os.path.join(TEACHER_UPLOAD_FOLDER, 'answers')
app.config['QUESTIONS_FOLDER'] = QUESTIONS_FOLDER
app.config['ANSWERS_FOLDER'] = ANSWERS_FOLDER


os.makedirs(app.config['TEACHER_UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['STUDENT_UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['QUESTIONS_FOLDER'], exist_ok=True)
os.makedirs(QUESTIONS_FOLDER, exist_ok=True)
os.makedirs(ANSWERS_FOLDER, exist_ok=True)


client = MongoClient('mongodb://localhost:27017/')
db = client['subj']
users_collection = db['users']


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if 'signup' in request.form:
            
            return redirect(url_for('student_signup'))

        
        student = users_collection.find_one({'role': 'student', 'username': username, 'password': password})
        if student:
            
            return redirect(url_for('student_success', username=username))
        else:
            
            return redirect(url_for('student_login'))

    return render_template('student_login.html')

@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if 'signup' in request.form:
            
            return redirect(url_for('teacher_signup'))

       
        teacher = users_collection.find_one({'role': 'teacher', 'username': username, 'password': password})
        if teacher:
            
            return redirect(url_for('teacher_success', username=username))
        else:
            
            return redirect(url_for('teacher_login'))

    return render_template('teacher_login.html')

@app.route('/teacher_success/<username>', methods=['GET', 'POST'])
def teacher_success(username):
    message = None

    if request.method == 'POST':
        
        question_file = request.files.get('question_document')
        answer_file = request.files.get('answer_document')

        if question_file:
            save_path = os.path.join(app.config['QUESTIONS_FOLDER'], question_file.filename)
            question_file.save(save_path)
            message = "Question uploaded successfully."

        if answer_file:
            save_path = os.path.join(app.config['ANSWERS_FOLDER'], answer_file.filename)
            answer_file.save(save_path)
            message = "Answer uploaded successfully."

    return render_template('teacherpage.html', username=username, message=message)



@app.route('/student_success/<username>', methods=['GET', 'POST'])
def student_success(username):
    message = None
    question_content = None  
    if request.method == 'POST':
        
        if 'text_document' in request.files:
            file = request.files['text_document']
            if file.filename != '':
                
                upload_folder = app.config['STUDENT_UPLOAD_FOLDER']
                filename = os.path.join(upload_folder, file.filename)
                file.save(filename)

                
                message = "File uploaded successfully."

    
    question_file_path = os.path.join(app.config['QUESTIONS_FOLDER'], 'questions.txt')
    question_content = read_file_content(question_file_path)

    
    return render_template('studentpage.html', username=username, message=message, question_content=question_content)


def read_file_content(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return None

@app.route('/student_signup', methods=['GET', 'POST'])
def student_signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        
        if not users_collection.find_one({'role': 'student', 'username': username}):
            
            users_collection.insert_one({'role': 'student', 'username': username, 'password': password})
            return redirect(url_for('student_success', username=username))
        else:
            
            return redirect(url_for('student_signup'))

    return render_template('student_signup.html')

@app.route('/teacher_signup', methods=['GET', 'POST'])
def teacher_signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        
        if not users_collection.find_one({'role': 'teacher', 'username': username}):
           
            users_collection.insert_one({'role': 'teacher', 'username': username, 'password': password})
            return redirect(url_for('teacher_success', username=username))
        else:
            
            return redirect(url_for('teacher_signup'))

    return render_template('teacher_signup.html')

@app.route('/upload_text_document', methods=['POST'])
def upload_text_document():
    if 'text_document' in request.files:
        file = request.files['text_document']
        if file.filename != '':
            username = request.form['username']  

            
            upload_folder = app.config['TEACHER_UPLOAD_FOLDER'] if user_is_teacher(username) else app.config['STUDENT_UPLOAD_FOLDER']

            
            filename = os.path.join(upload_folder, file.filename)
            file.save(filename)
            return "File uploaded successfully."

    
    return "No file selected."

def user_is_teacher(username):

    teacher = users_collection.find_one({'role': 'teacher', 'username': username})
    return teacher is not None

@app.route('/result_page/<username>', methods=['GET'])
def result_page(username):
    
    student_file_path = get_latest_file_path('stu_upload')

   
    reference_file_path = os.path.join(app.config['ANSWERS_FOLDER'], 'answers.txt')

    
    student_answer = process_text_file(student_file_path)
    reference_answer = process_text_file(reference_file_path)

    cosine_sim_score = calculate_cosine_similarity([student_answer, reference_answer])
    keywords_match_score = calculate_keywords_match_score(student_answer, reference_answer)


    score = ((4/ 10) * cosine_sim_score) + ((6 / 10) * keywords_match_score)

    if score >= 10:
        score = 10

 
    matches = tool.check(student_answer)

    
    if score < 0:
        score = 0

   
    return render_template('result_page.html', username=username, score=score, student_content=student_answer, reference_content=reference_answer,matches=len(matches))

def stemmer(keywords_list):
    ps = PorterStemmer()
    for i in range(len(keywords_list)):
        keywords_list[i] = ps.stem(keywords_list[i])
    return keywords_list

def lemmatize(keywords_list):
    lemmatizer = WordNetLemmatizer()
    for i in range(len(keywords_list)):
        keywords_list[i] = lemmatizer.lemmatize(keywords_list[i])
    return keywords_list

def get_latest_file_path(folder):
    files = os.listdir(folder)
    files = [os.path.join(folder, file) for file in files]
    return max(files, key=os.path.getctime)

def process_text_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    return text

def calculate_cosine_similarity(corpus):
    vectorizer = TfidfVectorizer()
    trsfm = vectorizer.fit_transform(corpus)
    score = cosine_similarity(trsfm[0], trsfm)[0][1] * 10
    return round(score, 2)

def calculate_keywords_match_score(answer, correct_answer):
    rake_nltk_var.extract_keywords_from_text(answer)
    keywords_answer_list = rake_nltk_var.get_ranked_phrases()

    rake_nltk_var.extract_keywords_from_text(correct_answer)
    keywords_correct_answer_list = rake_nltk_var.get_ranked_phrases()

    common_keywords = len(set(keywords_answer_list) & set(keywords_correct_answer_list))
    unique_keywords = len(set(keywords_answer_list + keywords_correct_answer_list))
    keywords_match_score = (common_keywords / unique_keywords) * 10

    return round(keywords_match_score, 2)

if __name__ == '__main__':
    app.run(debug=True)
