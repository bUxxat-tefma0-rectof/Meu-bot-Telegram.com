import os
import stripe
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
DOMAIN = os.getenv("DOMAIN", "https://seu-app.onrender.com")

stripe.api_key = STRIPE_API_KEY
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Produtos de exemplo
PRODUCTS = {
    "prod_1": {"name": "Camiseta Demo", "desc": "Camiseta de teste", "amount": 2500, "currency": "brl"},
    "prod_2": {"name": "Caneca Demo", "desc": "Caneca personalizada", "amount": 1500, "currency": "brl"},
    "prod_3": {"name": "Curso Demo", "desc": "Curso introdutório", "amount": 5000, "currency": "brl"},
}

def telegram_send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    # Quando usuário envia mensagem normal
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        kb = [[{"text": p["name"], "callback_data": f"buy:{pid}"}] for pid, p in PRODUCTS.items()]
        reply_markup = {"inline_keyboard": kb}
        telegram_send_message(chat_id, "Escolha um produto:", reply_markup)
        return jsonify(ok=True)

    # Quando usuário clica em botão
    if "callback_query" in data:
        cq = data["callback_query"]
        chat_id = cq["message"]["chat"]["id"]
        user = cq["from"]
        callback_data = cq["data"]

        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": cq["id"]})

        if callback_data.startswith("buy:"):
            prod_id = callback_data.split(":")[1]
            product = PRODUCTS.get(prod_id)
            if not product:
                telegram_send_message(chat_id, "Produto inválido.")
                return jsonify(ok=True)

            full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()

            customer = stripe.Customer.create(
                name=full_name or "Cliente Telegram",
                metadata={"telegram_id": str(user.get("id"))},
            )

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                customer=customer.id,
                line_items=[{
                    "price_data": {
                        "currency": product["currency"],
                        "product_data": {"name": product["name"], "description": product["desc"]},
                        "unit_amount": product["amount"],
                    },
                    "quantity": 1,
                }],
                success_url=f"{DOMAIN}/success",
                cancel_url=f"{DOMAIN}/cancel",
            )

            telegram_send_message(chat_id, f"✅ Link de pagamento: {session.url}")
    return jsonify(ok=True)

@app.route("/success")
def success():
    return "Pagamento concluído com sucesso! 🎉"

@app.route("/cancel")
def cancel():
    return "Pagamento cancelado. ❌"

@app.route("/")
def home():
    return "Bot de Pagamento Telegram + Stripe ativo ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
