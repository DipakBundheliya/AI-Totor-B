from flask import Flask , jsonify , request
from flask_cors import CORS
from pymongo import MongoClient
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_groq import ChatGroq
from langchain_mongodb.chat_message_histories import MongoDBChatMessageHistory
from passlib.hash import pbkdf2_sha256
from uuid import uuid4
import os 
from dotenv import load_dotenv
import prompt
import json

app = Flask(__name__)
CORS(app)
  
# MongoDB Connection
load_dotenv()
username = os.getenv("MONGO_USERNAME")
password = os.getenv("MONGO_PASSWORD")
client = MongoClient(f"mongodb+srv://{username}:{password}@cluster0.hpg57sk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db=client['my_db']
chat_collection=db["chat_histories"]
user_collection=db["user_data"]


system_prompt = prompt.system_prompt()
groq_api_key = os.getenv("GROQ_API_KEY")

chat = ChatGroq(temperature=0 ,groq_api_key=groq_api_key , model_name="llama3-70b-8192")
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}"),
    ]
)
chain = prompt | chat
chain_with_history = RunnableWithMessageHistory(
    chain,
    lambda session_id: MongoDBChatMessageHistory(
        session_id=session_id,
        connection_string=f"mongodb+srv://{username}:{password}@cluster0.hpg57sk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0",
        database_name="my_db",
        collection_name="chat_histories",
    ),
    input_messages_key="question",
    history_messages_key="history",
)

@app.route('/' , methods=["POST","GET"] )
def main():
    return jsonify({'message' : 'API calls successfully'}) , 201

@app.route('/register' , methods=["POST"] )
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if user_collection.find_one({'username':username}):
        return jsonify({'message':'Username already exists!'}) , 400

    hashed_password = pbkdf2_sha256.hash(password)

    user_collection.insert_one({
        'username': username,
        'password': hashed_password
    })
    return jsonify({'message' : 'User registered successfully'}) , 201


@app.route('/login' , methods=["POST"] )
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    user = user_collection.find_one({'username':username})
    
    if user:
        if  pbkdf2_sha256.verify(password , user["password"]):
            return jsonify({ 'message' : 'Login Successful!'}) , 200
        return jsonify({ 'message' : 'Password is not correct'}) , 401
    else:
        return jsonify({ 'message' : 'Invalid username' }) , 401  

@app.route('/logout' , methods=["POST"])
def logout():
    data = request.json
    username = data.get("username")
    result = user_collection.delete_one({'username' : username})
    if result.deleted_count == 1:
        return jsonify({ 'message' : 'Logout successfully' }) , 201  
    else:
        return jsonify({ 'message' : 'User not found in database' }) , 401  

@app.route('/chat' , methods=['POST'])
def chat():
    data = request.json
    SessionId = data.get('SessionId') 
    question = data.get('question') 
    if not SessionId:
        SessionId = str(uuid4())
    
    config = {"configurable": {"session_id": SessionId}}
    response = chain_with_history.invoke({"question": question}, config=config)
    print(response)
    return jsonify({
        'response' : str(response.content) , 
        'SessionId' : SessionId
    }) , 200

@app.route('/history' , methods=['POST'])
def history():
    user_chats = []
    data = request.json
    SessionId = data.get('SessionId')
    try :
        cur = chat_collection.find({"SessionId":SessionId})
        for doc in cur:
            role = json.loads(doc["History"])['type'] 
            content = json.loads(doc["History"])['data']['content']
            user_chats.append({'role':role , 'content':content})
        return jsonify({
            'response' : user_chats
        }) , 200
    except:
        return jsonify({
            'response' : 'error while fetching chat history'
        }) , 400
        
    
app.run(debug=True)