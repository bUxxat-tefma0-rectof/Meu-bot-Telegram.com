import os
import stripe
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# === CONFIGURAÇÕES ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
DOMAIN = os.getenv("DOMAIN", "https://seuapp.onrender.com")  # altere no Render

stripe.api_key = STRIPE_API_KEY
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# === OPÇÕES DE RECARGA ===
RECHARGES = {
    "rec_10": {"label": "💰 R$10,00", "amount": 1000},
    "rec_20": {"label": "💸 R$20,00", "amount": 2000},
    "rec_50": {"label": "💵 R$50,00", "amount": 5000},
}

# === FUNÇÃO AUXILIAR PARA ENVIAR MENSAGEM ===
def telegram_send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

# === ROTA PRINCIPAL DO TELEGRAM ===
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    # Quando o usuário envia uma mensagem comum
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        kb = [[{"text": v["label"], "callback_data": k}] for k, v in RECHARGES.items()]
        reply_markup = {"inline_keyboard": kb}
        telegram_send_message(chat_id, "💵 Escolha o valor que deseja recarregar:", reply_markup)
        return jsonify(ok=True)

    # Quando o usuário clica em um botão
    if "callback_query" in data:
        cq = data["callback_query"]
        chat_id = cq["message"]["chat"]["id"]
        user = cq["from"]
        callback_data = cq["data"]

        # Confirma o clique para parar o "loading" no Telegram
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": cq["id"]})

        # Se clicou em um valor de recarga
        if callback_data in RECHARGES:
            recharge = RECHARGES[callback_data]
            amount = recharge["amount"]
            label = recharge["label"]

            # Cria o cliente Stripe
            full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            customer = stripe.Customer.create(
                name=full_name or "Cliente Telegram",
                metadata={"telegram_id": str(user.get("id"))},
            )

            # Cria a sessão de pagamento no Stripe
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                customer=customer.id,
                line_items=[{
                    "price_data": {
                        "currency": "brl",
                        "product_data": {"name": f"Recarga {label}"},
                        "unit_amount": amount,
                    },
                    "quantity": 1,
                }],
                success_url=f"{DOMAIN}/success",
                cancel_url=f"{DOMAIN}/cancel",
            )

            telegram_send_message(chat_id, f"✅ Clique para pagar {label}:\n{session.url}")
    return jsonify(ok=True)

# === PÁGINAS SIMPLES ===
@app.route("/success")
def success():
    return "Pagamento concluído com sucesso! 🎉"

@app.route("/cancel")
def cancel():
    return "Pagamento cancelado. ❌"

@app.route("/")
def home():
    return "🤖 Bot de Pagamento Telegram + Stripe está ativo!"

# === EXECUÇÃO LOCAL ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
