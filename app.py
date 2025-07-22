from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
import json
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# === Initialisation Flask ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'super_secret_key_à_personnaliser'  # 🔒 change ceci pour la prod

# === Chemins absolus ===
PRODUCTS_FILE = os.path.join(BASE_DIR, 'data', 'products.json')
USERS_FILE = os.path.join(BASE_DIR, 'data', 'users.json')
COMMANDES_FILE = os.path.join(BASE_DIR, 'data', 'commandes.json')

# === Charger variables .env ===
load_dotenv()

# === SMTP Config ===
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

ADMIN_PASSWORD = 'admin123'  # 🔒 change-le ici

# === Routes ===

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/produits')
def produits():
    try:
        with open(PRODUCTS_FILE, encoding='utf-8') as f:
            produits = json.load(f)
        print(f"✅ {len(produits)} produit(s) chargé(s) depuis {PRODUCTS_FILE}")
    except FileNotFoundError:
        print(f"❌ Le fichier {PRODUCTS_FILE} est introuvable.")
        produits = []
    except json.JSONDecodeError as e:
        print(f"❌ Erreur JSON dans {PRODUCTS_FILE} : {e}")
        produits = []
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")
        produits = []

    return render_template('products.html', produits=produits)

# Servir le static proprement
@app.route('/static/<path:filename>')
def custom_static(filename):
    return send_from_directory(app.static_folder, filename)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        nom = request.form.get('nom')
        message = request.form.get('message')
        
        # Dossier pour stocker les messages
        if not os.path.exists('data'):
            os.makedirs('data')

        # Fichier JSON des messages
        chemin = 'data/messages.json'
        if not os.path.exists(chemin):
            with open(chemin, 'w') as f:
                json.dump([], f)

        # Lire les anciens messages
        with open(chemin, 'r') as f:
            anciens = json.load(f)

        # Ajouter le nouveau
        nouveaux = {
            "nom": nom,
            "message": message
        }
        anciens.append(nouveaux)

        # Sauvegarder
        with open(chemin, 'w') as f:
            json.dump(anciens, f, indent=4)

        flash("Message bien reçu ! Merci de nous avoir contacté.", "success")
        return redirect(url_for('contact'))

    return render_template('contact.html')

# ========= Routes Admin =========
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('admin_login.html', error="Mot de passe incorrect")
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    # Charger les produits
    with open(PRODUCTS_FILE) as f:
        produits = json.load(f)

    # Ajout d’un produit
    if request.method == 'POST':
        nom = request.form['nom']
        prix = request.form['prix']
        image = request.form['image']

        produits.append({"nom": nom, "prix": prix, "image": image})
        with open(PRODUCTS_FILE, 'w') as f:
            json.dump(produits, f, indent=2)

        return redirect(url_for('admin_panel'))

    return render_template('admin.html', produits=produits)

@app.route('/admin/delete/<int:index>', methods=['POST'])
def delete_product(index):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    with open(PRODUCTS_FILE) as f:
        produits = json.load(f)

    if 0 <= index < len(produits):
        produits.pop(index)
        with open(PRODUCTS_FILE, 'w') as f:
            json.dump(produits, f, indent=2)

    return redirect(url_for('admin_panel'))

@app.route('/admin/commandes')
def admin_commandes():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    if os.path.exists('data/commandes.json'):
        with open('data/commandes.json') as f:
            commandes = json.load(f)
    else:
        commandes = []

    return render_template('admin_commandes.html', commandes=commandes)
    
@app.route('/admin/messages')
def voir_messages():
    chemin = 'data/messages.json'
    messages = []

    # Charger les messages s'ils existent
    if os.path.exists(chemin):
        with open(chemin, 'r') as f:
            try:
                messages = json.load(f)
            except json.JSONDecodeError:
                messages = []

    return render_template('admin_messages.html', messages=messages)

    # Ajout commande
@app.route('/commander/<int:index>', methods=['GET', 'POST'])
def commander(index):
    # Vérifie si l'utilisateur est connecté
    if 'user' not in session:
        flash('Veuillez vous connecter pour passer une commande.', 'warning')
        return redirect(url_for('login'))

    # Charger les produits
    with open(PRODUCTS_FILE) as f:
        produits = json.load(f)

    if index >= len(produits):
        return "Produit introuvable", 404

    produit = produits[index]

    if request.method == 'POST':
        nom = session['user']
        email = session['email']
        telephone = request.form['telephone']
        adresse = request.form['adresse']

        commande = {
            "produit": produit['nom'],
            "prix": produit['prix'],
            "nom_client": nom,
            "email": email,
            "telephone": telephone,
            "adresse": adresse,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if os.path.exists(COMMANDES_FILE):
            with open(COMMANDES_FILE) as f:
                commandes = json.load(f)
        else:
            commandes = []

        commandes.append(commande)
        with open(COMMANDES_FILE, 'w') as f:
            json.dump(commandes, f, indent=2)

        flash('Commande passée avec succès 🎉', 'success')
        return render_template('confirmation.html', produit=produit)

    return render_template('commande.html', produit=produit)

# ... tout le reste déjà présent ...

@app.route('/ajouter_au_panier/<int:index>')
def ajouter_au_panier(index):
    if 'user' not in session:
        flash('Veuillez vous connecter pour ajouter des articles au panier.', 'warning')
        return redirect(url_for('login'))

    with open(PRODUCTS_FILE) as f:
        produits = json.load(f)
    if index >= len(produits):
        return "Produit introuvable", 404

    panier = session.get('panier', [])
    panier.append(produits[index])
    session['panier'] = panier
    flash('Produit ajouté au panier !', 'success')
    return redirect(url_for('produits'))

@app.route('/panier')
def panier():
    if 'user' not in session:
        flash('Veuillez vous connecter pour voir votre panier.', 'warning')
        return redirect(url_for('login'))

    panier = session.get('panier', [])
    total = calcul_total(panier)
    return render_template('panier.html', panier=panier, total=total)
    
@app.route('/vider_panier')
def vider_panier():
    session.pop('panier', None)
    flash('Panier vidé.', 'info')
    return redirect(url_for('panier'))

@app.route('/supprimer_du_panier/<int:index>')
def supprimer_du_panier(index):
    panier = session.get('panier', [])
    if 0 <= index < len(panier):
        panier.pop(index)
        session['panier'] = panier
    return redirect(url_for('panier'))

def calcul_total(panier):
    total = 0
    for item in panier:
        prix_str = item['prix'].replace('FCFA', '').replace(' ', '')
        try:
            total += int(prix_str)
        except:
            pass
    return total

#suite code de ajout panier global

@app.route('/commander_panier', methods=['GET', 'POST'])
def commander_panier():
    if 'user' not in session:
        flash('Veuillez vous connecter pour passer commande.', 'warning')
        return redirect(url_for('login'))

    panier = session.get('panier', [])
    if not panier:
        return redirect(url_for('panier'))

    if request.method == 'POST':
        nom = session['user']
        email = session['email']
        telephone = request.form['telephone']
        adresse = request.form['adresse']

        commande = {
            "produits": panier,
            "nom_client": nom,
            "email": email,
            "telephone": telephone,
            "adresse": adresse,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(COMMANDES_FILE) as f:
            commandes = json.load(f)
        commandes.append(commande)
        with open(COMMANDES_FILE, 'w') as f:
            json.dump(commandes, f, indent=2)
        session['panier'] = []
        flash('Commande passée avec succès 🎉', 'success')
        return render_template('confirmation.html', multiple=True)

    return render_template('commande_panier.html', panier=panier)
    
# Configuration SMTP
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

@app.route('/send_message', methods=['POST'])
def send_message():
    nom = request.form['nom']
    email = request.form['email']
    message = request.form['message']

    content = f"Nom: {nom}\nEmail: {email}\nMessage:\n{message}"
    msg = MIMEText(content)
    msg['Subject'] = 'Nouveau message via formulaire Serpillères Pro Bella'
    msg['From'] = email
    msg['To'] = SMTP_USERNAME

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        flash("✉️ Message envoyé avec succès ✅", "success")
    except Exception as e:
        flash("❌ Une erreur s'est produite lors de l'envoi.", "error")
        print(e)

    return redirect(url_for('home'))


@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form['newsletter_email']
    content = f"Nouveau abonné newsletter : {email}"
    msg = MIMEText(content)
    msg['Subject'] = 'Nouvel abonnement newsletter Serpillères Pro Bella'
    msg['From'] = SMTP_USERNAME
    msg['To'] = SMTP_USERNAME

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        flash("✅ Abonnement effectué avec succès !", "success")
    except Exception as e:
        flash("❌ Une erreur s'est produite pendant l’abonnement.", "error")
        print(e)

    return redirect(url_for('home'))
    
# utilisateurs 

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

# === Authentification ===

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form['nom']
        email = request.form['email']
        password = request.form['password']

        users = load_users()
        if any(u['email'] == email for u in users):
            flash('Cet email est déjà utilisé.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        user = {"nom": nom, "email": email, "password": hashed_password}
        users.append(user)
        save_users(users)

        flash('Inscription réussie. Connectez-vous.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        users = load_users()
        user = next((u for u in users if u['email'] == email), None)

        if user and check_password_hash(user['password'], password):
            session['user'] = user['nom']
            session['email'] = user['email']
            session['panier'] = []
            flash(f'Bienvenue {user["nom"]} 👋', 'success')
            return redirect(url_for('home'))
        else:
            flash('Email ou mot de passe incorrect.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Déconnexion réussie.', 'info')
    return redirect(url_for('home'))
    
@app.route('/recherche')
def recherche():
    query = request.args.get('q', '').lower()
    produits_disponibles = [
        {'nom': 'Serpillère classique', 'description': 'Une serpillière traditionnelle en coton'},
        {'nom': 'Serpillère microfibre', 'description': 'Très absorbante et facile à nettoyer'},
        {'nom': 'Serpillère Pro Max', 'description': 'Idéale pour les grandes surfaces'},
    ]
    
    # Recherche dans le nom (tu peux ajouter la description aussi)
    resultats = [
        p for p in produits_disponibles if query in p['nom'].lower()
    ]

    return render_template('recherche.html', produits=resultats, query=query)

    
# 🚀 Chatbot dynamique et enrichi
questions_reponses = {
    # Livraison
    ("livraison", "délai", "temps", "expédition", "envoyer", "apporter", "retard"): 
        "🚚 *Livraison rapide !* Nous livrons sous 48h à Cotonou et 72h dans les autres villes. Les frais de déplacement varient selon votre localisation.",

    # Retour & Remboursement
    ("retour", "remboursement", "échanger", "changer", "revenir", "annuler"): 
        "🔄 *Retours acceptés* sous 7 jours. Contactez l’assistance pour plus d’informations.",

    # Prix & qualités
    ("prix", "coût", "combien", "tarif", "montant", "devise", "euro", "dollar", "$", "£", "₣", "valeur", "budget", "payer", "choix"): 
        "💰 Les tarifs varient selon le modèle, la taille et la qualité choisie. Nous proposons plusieurs gammes accessibles à tous les budgets, avec des options standard, éco et premium. Pour un devis précis, n’hésitez pas à nous écrire !",

    # Paiement
    ("paiement", "payer", "mode", "mobile money", "espèces", "crypto", "bitcoin", "à la livraison"): 
        "💳 Modes de paiement disponibles : Mobile Money, espèces, crypto-monnaies (Bitcoin, Ethereum, Litecoin, USDT, TON...) ou paiement à la livraison ✅. Pour les paiements en ligne, merci d’envoyer une capture d’écran à notre assistance WhatsApp (+229 0151782679).",

    # Fidélité & Réductions
    ("promo", "réduction", "offre", "promotion", "fidélité", "bonus", "client fidèle"): 
        "🎁 *Offres en cours* :\n- ✅ 10 serpillères achetées ou plus = -10% de réduction !\n- ✅ 5 serpillères achetées ou plus = -5%.\n📌 Les clients fidèles bénéficient d’offres exclusives. 🎉",

    # Contact
    ("contact", "joindre", "parler", "numéro", "whatsapp", "téléphone", "assistance", "support"): 
        "📱 *Nous sommes là pour vous !* Contactez l’assistance sur WhatsApp au +229 0151782679 ou via le formulaire du site. N'oubliez pas de laisser votre numéro de téléphone dans la partie message pour un retour rapide.",

    # Qualité produit
    ("qualité", "matière", "composition", "durée", "résistant", "sol", "lavage"): 
        "🧼 Nos serpillères sont en microfibre renforcée, très résistantes et adaptées à tout type de sol (carrelage, parquet, béton, etc.). Lavables et réutilisables plusieurs fois !",

    # Utilisation
    ("utiliser", "nettoyage", "comment", "mode d’emploi", "manuel", "entretenir"): 
        "📘 Astuce : Utilisez-les sèches pour la poussière ou humides pour un nettoyage impeccable. Après usage, un simple rinçage à l’eau suffit.",

    # Commande
    ("commande", "acheter", "achat", "commander", "panier", "finaliser"): 
        "🛒 Ajoutez vos produits au panier et finalisez la commande. Vous devez être connecté(e) pour passer commande ✅. Un conseiller peut aussi vous aider par WhatsApp si besoin.",

    # Suivi
    ("suivi", "tracking", "où est ma commande", "numéro de commande", "statut"): 
        "📦 Donnez-moi votre numéro de commande et je vérifie son statut pour vous. Sinon, notre équipe vous tiendra informé dès l’expédition !",

    # Livraison spéciale
    ("distance", "loin", "transport", "déplacement", "zone"): 
        "🚗 Si vous êtes hors de Cotonou, les frais de déplacement sont à votre charge. Vous pouvez aussi venir récupérer votre commande directement chez nous pour économiser sur les frais.",
}

def trouver_reponse(message):
    """ Trouve une réponse basée sur les mots-clés """
    message = message.lower()
    for mots_cles, reponse in questions_reponses.items():
        if any(mot in message for mot in mots_cles):
            return reponse
    return "🤖 Je ne comprends pas encore cela. Reformule ou contacte notre assistant WhatsApp."

# ===== Routes =====
@app.route('/assistant')
def assistant():
    return render_template('assistant.html')

@app.route('/chatbot', methods=['POST'])
def chatbot():
    if not request.is_json:
        return jsonify({'error': 'Expected JSON data'}), 415

    data = request.get_json()
    user_message = data.get('message', '')
    bot_response = trouver_reponse(user_message)
    return jsonify({'reponse': bot_response})

    
@app.route('/avis')
def avis():
    return render_template('avis.html')

    
if __name__ == '__main__':
    app.run(debug=True)

