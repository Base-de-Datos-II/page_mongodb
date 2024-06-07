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
    pipeline = [
        {
            "$addFields": {
                "age": {
                    "$subtract": [{"$year": "$$NOW"}, {"$year": "$FECHA_NACIMIENTO"}]
                }
            }
        },
        {
            "$group": {
                "_id": None,
                "age_ranges": {
                    "$push": {
                        "age": "$age",
                        "range": {
                            "$switch": {
                                "branches": [
                                    {"case": {"$lt": ["$age", 18]}, "then": "<18"},
                                    {"case": {"$and": [{"$gte": ["$age", 18]}, {"$lte": ["$age", 25]}]}, "then": "18-25"},
                                    {"case": {"$and": [{"$gte": ["$age", 26]}, {"$lte": ["$age", 35]}]}, "then": "26-35"},
                                    {"case": {"$and": [{"$gte": ["$age", 36]}, {"$lte": ["$age", 50]}]}, "then": "36-50"},
                                    {"case": {"$gt": ["$age", 50]}, "then": "50+"}
                                ],
                                "default": "Unknown"
                            }
                        }
                    }
                }
            }
        },
        {
            "$unwind": "$age_ranges"
        },
        {
            "$group": {
                "_id": "$age_ranges.range",
                "count": {"$sum": 1}
            }
        }
    ]

    result = list(usuarios.aggregate(pipeline))
    edades_lectores_data = {
        "ageRanges": ["<18", "18-25", "26-35", "36-50", "50+"],
        "counts": [0, 0, 0, 0, 0]
    }
    range_map = {"<18": 0, "18-25": 1, "26-35": 2, "36-50": 3, "50+": 4}

    for item in result:
        if item["_id"] in range_map:
            edades_lectores_data["counts"][range_map[item["_id"]]] = item["count"]

    return edades_lectores_data

@app.route('/api/edades_lectores', methods=['GET'])
def get_edades_lectores_api():
    edades_lectores_data = get_edades_lectores()
    return jsonify({"edadesLectores": edades_lectores_data})





def get_libros_mas_pedidos():
    pipeline = [
        {"$unwind": "$LIBROS_PRESTADOS"},
        {"$match": {"LIBROS_PRESTADOS.COD_BARRAS": {"$ne": None, "$ne": "", "$ne": 0}}},
        {
            "$group": {
                "_id": "$LIBROS_PRESTADOS.COD_BARRAS",
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": 10},
        {
            "$lookup": {
                "from": "libros",
                "localField": "_id",
                "foreignField": "COD_BARRAS",
                "as": "libro"
            }
        },
        {"$unwind": {"path": "$libro", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 0,
                "titulo": "$libro.TITULO",
                "count": 1
            }
        }
    ]

    result = list(usuarios.aggregate(pipeline))
    return result


@app.route('/api/libros_mas_pedidos', methods=['GET'])
def get_libros_mas_pedidos_api():
    libros_mas_pedidos_data = get_libros_mas_pedidos()
    return jsonify({"librosMasPedidos": libros_mas_pedidos_data})


if __name__ == '__main__':
    app.run(debug=True)

