from flask import Flask, render_template, request, redirect, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
client = MongoClient("mongodb://localhost:27017/")
db = client.music_app
artisti = db.artisti
canzoni = db.canzoni

@app.route("/")
def home():
    return render_template("index.html")

################################## RICERCA DI CANZONI NELLA HOME #######################################

@app.route("/search")
def search():
    query = request.args.get("query", "").strip()

    if not query:
        return redirect("/")

    regex = {"$regex": query, "$options": "i"}

    canzoni_match = list(db.canzoni.aggregate([
        {
            "$lookup": {
                "from": "artisti",
                "localField": "artisti_id",
                "foreignField": "_id",
                "as": "artisti"
            }
        },
        {
            "$match": {
                "$or": [
                    {"titolo": regex},
                    {"artisti.nome": regex}
                ]
            }
        }
    ]))

    seen = set()
    risultati = []
    for c in canzoni_match:
        cid = str(c["_id"])
        if cid not in seen:
            c["_id"] = cid 
            for a in c.get("artisti", []):
                a["_id"] = str(a["_id"])
            risultati.append(c)
            seen.add(cid)

    return render_template("index.html", artisti=list(artisti.find()), canzoni=risultati, search=query)


##################  GESTIONE ARTISTI  #########################

@app.route("/artisti")
def pagina_artisti():
    query = request.args.get("query")
    if query:
        artisti_list = list(artisti.find({"nome": {"$regex": query, "$options": "i"}}).collation({"locale": "it", "strength": 1}).sort("nome", 1))
    else:
        artisti_list = list(artisti.find().collation({"locale": "it", "strength": 1}).sort("nome", 1))

    for a in artisti_list:
        a["_id"] = str(a["_id"])

    return render_template("artisti.html", artisti=artisti_list)


@app.route("/api/artisti")
def api_artisti():
    query = request.args.get("query", "").strip()
    if not query:
        artisti = list(db.artisti.find())
    else:
        regex = {"$regex": query, "$options": "i"}
        artisti = list(db.artisti.find({"nome": regex}))

    for a in artisti:
        a["_id"] = str(a["_id"])

    return jsonify(artisti)


@app.route("/api/counts")
def api_counts():
    num_artisti = db.artisti.count_documents({})
    num_canzoni = db.canzoni.count_documents({})
    return jsonify({"artisti": num_artisti, "canzoni": num_canzoni})


@app.route("/add_artista", methods=["POST"])
def add_artista():
    nome = request.form["nome"].strip()
    genere = request.form["genere"].strip()
    artisti.insert_one({"nome": nome, "genere": genere})
    return redirect("/artisti")


@app.route("/api/artisti/<id>", methods=["PUT"])
def update_artista(id):
    data = request.get_json()
    nome = data.get("nome").strip()
    genere = data.get("genere").strip()
    if not nome or not genere:
        return jsonify({"error": "Dati mancanti"}), 400
    db.artisti.update_one({"_id": ObjectId(id)}, {"$set": {"nome": nome, "genere": genere}})
    return jsonify({"success": True})


@app.route("/delete_artista/<id>")
def delete_artista(id):
    artisti.delete_one({"_id": ObjectId(id)})
    canzoni.delete_many({"artisti_id": ObjectId(id)})
    return redirect("/artisti")


######################  GESTIONE CANZONI  ########################

@app.route("/canzoni")
def pagina_canzoni():
    all_artisti = list(artisti.find())

    canzoni_join = list(db.canzoni.aggregate([
        {
            "$lookup": {
                "from": "artisti",
                "localField": "artisti_id",
                "foreignField": "_id",
                "as": "artisti"
            }
        },
        {
            "$sort": {"titolo": 1}
        }
    ], collation={"locale": "it", "strength": 1}))

    for c in canzoni_join:
        c["_id"] = str(c["_id"])
        for a in c.get("artisti", []):
            a["_id"] = str(a["_id"])

    return render_template("canzoni.html", artisti=all_artisti, canzoni=canzoni_join)


@app.route("/api/canzoni")
def api_canzoni():
    query = request.args.get("query", "").strip()
    regex = {"$regex": query, "$options": "i"}

    canzoni_match = list(db.canzoni.aggregate([
        {
            "$lookup": {
                "from": "artisti",
                "localField": "artisti_id",
                "foreignField": "_id",
                "as": "artisti"
            }
        },
        {
            "$match": {
                "$or": [
                    {"titolo": regex},
                    {"artisti.nome": regex}
                ]
            }
        },
        {
            "$sort": {
                "titolo": 1
            }
        }
    ]))

    for c in canzoni_match:
        if isinstance(c.get("_id"), ObjectId):
            c["_id"] = str(c["_id"])

        if "artisti_id" in c:
            c["artisti_id"] = [str(aid) for aid in c["artisti_id"]]

        for a in c.get("artisti", []):
            if isinstance(a.get("_id"), ObjectId):
                a["_id"] = str(a["_id"])

    return jsonify(canzoni_match)

 
@app.route("/api/canzoni/<id>", methods=["PUT"])
def update_canzone(id):
    data = request.get_json()
    titolo = data.get("titolo").strip()
    anno = data.get("anno")

    if not titolo or not anno:
        return jsonify({"error": "Dati mancanti"}), 400

    db.canzoni.update_one(
        {"_id": ObjectId(id)},
        {"$set": {"titolo": titolo, "anno": anno}}
    )

    return jsonify({"success": True})


@app.route("/add_canzone", methods=["POST"])
def add_canzone():
    titolo = request.form["titolo"].strip()
    anno = int(request.form["anno"])
    artisti_id_str = request.form["artisti_id"]

    if not artisti_id_str:
        return "Error. Nessun artista selezionato", 400
    
    artisti_id = [ObjectId(aid) for aid in artisti_id_str.split(",") if aid.strip()]

    canzone = {
        "titolo": titolo,
        "anno": anno,
        "artisti_id": artisti_id
    }

    canzoni.insert_one(canzone)
    return redirect("/canzoni")


@app.route("/delete_canzone/<id>")
def delete_canzone(id):
    canzoni.delete_one({"_id": ObjectId(id)})
    return redirect("/canzoni")

###############################################

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)