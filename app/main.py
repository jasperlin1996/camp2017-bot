import json

from flask import Flask, request, jsonify

from models import db, Team, Coupon
from error import Error

import config

import telepot
import telepot.helper
from telepot.loop import OrderedWebhook
from telepot.delegate import (
    per_chat_id, create_open, pave_event_space, include_callback_query_chat_id)

with open('produce-permission.json', 'r') as produce_permission_json:
    produce_permission = json.load(produce_permission_json)

with open('teams.json', 'r') as teams_json:
    teams = json.load(teams_json)

app = Flask(__name__)
app.config.from_pyfile('config.py')
db.init_app(app)

for _ in teams:
    try:
        Team(group_id=_['groupId'], name=_['name']).save()
    except:
        pass


@app.route('/generate', methods=['POST'])
def generate():
    token = request.form.get('token')
    coin = request.form.get('coin')
    description = request.form.get('description')

    if token not in produce_permission.keys():
        raise Error("invalid token")

    if coin is None or description is None:
        raise Error("coin and description required")

    coupon = Coupon(coin=coin, description=description, producer=produce_permission[token])

    try:
        coupon.save()
    except:
        raise Error("invalid value")

    return jsonify({'status': 'OK', 'coupon': str(coupon.id)})


@app.route('/consume', methods=['POST'])
def consume():
    group_id = request.form.get('group_id')
    coupon_id = request.form.get('coupon')

    if group_id is None or coupon_id is None:
        raise Error("group_id and coupon required")

    try:
        coupon = Coupon.objects.with_id(coupon_id)
    except:
        raise Error("invalid coupon id")

    if coupon is None:
        raise Error("invalid coupon id")

    if coupon.own_team is None:
        try:
            team = Team.objects(group_id=group_id).get()
        except:
            raise Error("invalid team id")

        Team.objects(group_id=group_id).update_one(inc__coin=coupon.coin)
        team.reload()
        coupon.own_team = team
        coupon.save()
        bot.sendMessage(team.group_id, "恭喜獲得 {} SITCON Coin\n{} 目前總計擁有 {} SITCON Coin".format(coupon.coin, team.name, team.coin))

        return jsonify({'status': 'OK'})
    else:
        raise Error("Already used", status_code=409)


@app.route('/status')
def status():
    return Team.objects().to_json()


@app.route('/webhook', methods=['GET', 'POST'])
def pass_update():
    webhook.feed(request.data)
    return 'OK'


@app.errorhandler(Error)
def handle_error(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


class TGHandler(telepot.helper.ChatHandler):
    def on_callback_query(self, msg):
        self.bot.answerCallbackQuery(msg['id'], url="https://camp.sitcon.party?id=" + str(msg['message']['chat']['id']))


bot = telepot.DelegatorBot(config.BOT_TOKEN, [
    include_callback_query_chat_id(
        pave_event_space())(
            per_chat_id(), create_open, TGHandler, timeout=10),
])

webhook = OrderedWebhook(bot)

try:
    bot.setWebhook(config.WEBHOOK_URI)
except telepot.exception.TooManyRequestsError:
    pass

webhook.run_as_thread()
