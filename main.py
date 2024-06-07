from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from bson.json_util import dumps
from datetime import datetime

app = Flask(__name__)

# MongoDB connection configuration
client = MongoClient("mongodb+srv://user:user@cluster0.0t7rmyi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client['biblioteca']
usuarios = db['usuarios']
libros = db['libros']

# Initial data limit for lazy loading
INITIAL_DATA_LIMIT = 10

@app.route('/usuarios')
def user():
    return render_template('users_page.html')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/libros')
def book():
    return render_template('books_page.html')
@app.route('/estadisticas')
def estadisticas():
    return render_template('estadisticas.html')
@app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', INITIAL_DATA_LIMIT))
    skip = (page - 1) * limit

    search_query = request.args.get('search_query', '').strip()
    projection = {"LIBROS_PRESTADOS": 1, "NOMBRE": 1, "CORREO": 1}  # Project only necessary fields

    query = {}
    if search_query:
        query["$or"] = [{"NOMBRE": {"$regex": search_query, "$options": "i"}}, {"CORREO": {"$regex": search_query, "$options": "i"}}]

    usuarios_cursor = usuarios.find(query, projection).skip(skip).limit(limit)
    all_usuarios = list(usuarios_cursor)

    # Obtener detalles de los libros prestados en una sola consulta
    codigos_barras = [libro["COD_BARRAS"] for usuario in all_usuarios for libro in usuario['LIBROS_PRESTADOS']]
    libros_info = libros.find({"COD_BARRAS": {"$in": codigos_barras}})
    libros_dict = {libro["COD_BARRAS"]: libro for libro in libros_info}

        # Reemplazar COD_BARRAS con detalles del libro en cada usuario utilizando una lista de comprensión
    all_usuarios = [{
        **usuario,
        'LIBROS_PRESTADOS': [libros_dict.get(libro["COD_BARRAS"]) for libro in usuario['LIBROS_PRESTADOS'] if libros_dict.get(libro["COD_BARRAS"])]
    } for usuario in all_usuarios]

    return dumps(all_usuarios)

@app.route('/api/libros', methods=['GET'])
def get_libros():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', INITIAL_DATA_LIMIT))
    skip = (page - 1) * limit

    search_query = request.args.get('search_query', '').strip()
    projection = {"_id": 0}  # Exclude _id field from result

    query = {}
    if search_query:
        query["$or"] = [{"TITULO": {"$regex": search_query, "$options": "i"}}, {"AUTOR": {"$regex": search_query, "$options": "i"}}]

    libros_cursor = libros.find(query, projection).skip(skip).limit(limit)
    all_libros = list(libros_cursor)

    return dumps(all_libros)





def get_edades_lectores():
    now = datetime.now()
    usuarios_con_edad = usuarios.find({"FECHA_NACIMIENTO": {"$exists": True}})
    edades_lectores = [(now.year - datetime.utcfromtimestamp(usuario["FECHA_NACIMIENTO"].timestamp()).year) for usuario in usuarios_con_edad]
    edades_lectores_data = {
        "ageRanges": ["<18", "18-25", "26-35", "36-50", "50+"],
        "counts": [
            sum(1 for edad in edades_lectores if edad < 18),
            sum(1 for edad in edades_lectores if 18 <= edad <= 25),
            sum(1 for edad in edades_lectores if 26 <= edad <= 35),
            sum(1 for edad in edades_lectores if 36 <= edad <= 50),
            sum(1 for edad in edades_lectores if edad > 50)
        ]
    }
    return edades_lectores_data

@app.route('/api/edades_lectores', methods=['GET'])
def get_edades_lectores_api():
    edades_lectores_data = get_edades_lectores()
    return jsonify({"edadesLectores": edades_lectores_data})





def get_libros_mas_pedidos():
    libros_mas_pedidos = usuarios.aggregate([
        {"$unwind": "$LIBROS_PRESTADOS"},
        {"$group": {
            "_id": "$LIBROS_PRESTADOS.COD_BARRAS",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ])
    
    # Obtener los códigos de barras de los libros más pedidos
    codigos_barras_mas_pedidos = [libro["_id"] for libro in libros_mas_pedidos]
    
    # Buscar los títulos de los libros en la colección "libros"
    libros_mas_pedidos_data = libros.find(
        {"COD_BARRAS": {"$in": codigos_barras_mas_pedidos}, "TITULO": {"$ne": "No Title"}},
        {"TITULO": 1, "_id": 0}
    )
    
    # Construir un diccionario para contar las ocurrencias de cada título
    count_dict = {}
    for libro in libros_mas_pedidos_data:
        titulo = libro["TITULO"]
        if titulo in count_dict:
            count_dict[titulo] += 1
        else:
            count_dict[titulo] = 1
    
    # Construir la lista de resultados
    libros_mas_pedidos_result = [{"titulo": titulo, "count": count_dict[titulo]} for titulo in count_dict]
    
    return libros_mas_pedidos_result

@app.route('/api/libros_mas_pedidos', methods=['GET'])
def get_libros_mas_pedidos_api():
    libros_mas_pedidos_data = get_libros_mas_pedidos()
    return jsonify({"librosMasPedidos": libros_mas_pedidos_data})


if __name__ == '__main__':
    app.run(debug=True)

