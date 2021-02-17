import telebot
import config
import sqlite3
import json

from firebase import firebase
from json import JSONEncoder
from telebot import types


global bot
global db
global sql
global fb

bot = telebot.TeleBot(config.TOKEN)
db = sqlite3.connect('server.db', check_same_thread = False)
sql = db.cursor()
fb = firebase.FirebaseApplication('URL_TO_FIREBASE_DATABASE', None)

sql.execute("""CREATE TABLE IF NOT EXISTS admins (
	username TEXT,
	status TEXT,
	is_running BOOLEAN
)""")
db.commit()

class Post:
	def __init__(self, post_id, liked_users, disliked_users):
		self.post_id = post_id
		self.liked_users = liked_users
		self.disliked_users = disliked_users

class DataEncoder(JSONEncoder):
	def default(self, o):
		return o.__dict__

sql.execute(f"SELECT status FROM admins WHERE status = '{config.super_admin}'")
if sql.fetchone() is None:
	sql.execute(f"INSERT INTO admins VALUES (?, ?, ?)", (config.s_a_name, config.super_admin, 0)) 
	db.commit()

def get_start_ui(message):
	st_markup = types.ReplyKeyboardMarkup(resize_keyboard = True, one_time_keyboard = True)
	item1 = types.KeyboardButton("Начать сессию")
	st_markup.add(item1)

	if(message.from_user.username == config.s_a_name):
		item2 = types.KeyboardButton("Добавить администратора")
		st_markup.add(item2)

	return st_markup

@bot.message_handler(commands=['start'])
def start(message):
	st = open('res/sticker.webp', 'rb')

	st_markup = get_start_ui(message)

	bot.send_sticker(message.chat.id, st, reply_markup = st_markup)

@bot.message_handler(content_types = ['text'])
def main(message):
	if message.chat.type == 'private':
		username = message.from_user.username

		if message.text == 'Начать сессию':
			sql.execute(f"SELECT username FROM admins WHERE username = '{username}'")
			if sql.fetchone() is None:
				bot.send_message(message.chat.id, "❌Вы не являетесь администратором! В доступе отказано!❌")
			else:
				sql.execute(f"SELECT is_running FROM admins WHERE is_running = 1")
				if sql.fetchone() is None:
					fn_markup = types.ReplyKeyboardMarkup(resize_keyboard = True, one_time_keyboard = True)
					item_fn = types.KeyboardButton("Завершить сессию")
					fn_markup.add(item_fn)

					sql.execute(f'UPDATE admins SET is_running = 1 WHERE username = "{username}"')
					db.commit()

					in_username = username
					if in_username == config.s_a_name:
						in_username = "Повелитель"

					bot.send_message(message.chat.id, ("✅Добро пожаловать, <b>%s</b>! Сессия начата✅" % in_username), 
						parse_mode = 'html', reply_markup = fn_markup)
				else:
					bot.send_message(message.chat.id, "❌Похоже кто-то запустил сессию до вас. Дождитесь ёё завершения.❌")
		elif message.text == 'Завершить сессию':
			sql.execute(f'UPDATE admins SET is_running = 0 WHERE username = "{username}"')
			db.commit()

			st_markup = get_start_ui(message)

			bot.send_message(message.chat.id, "Сессия завершена!", reply_markup = st_markup)
		elif message.text == 'Добавить администратора':
			if username == config.s_a_name:
				bot.send_message(message.chat.id, "Введите имя пользователя, которого хотите добавить (не забудьте дописать @ перед именем): ")
			else:
				bot.send_message(message.chat.id, "❌Вы не являетесь главным администратором! В доступе отказано!❌")
		elif message.text[0] == "@" and username == config.s_a_name:
			sql.execute(f"SELECT username FROM admins WHERE username = '{message.text[1:]}'")
			if sql.fetchone() is None:
				sql.execute(f"INSERT INTO admins VALUES (?, ?, ?)", (message.text[1:], config.admin, False)) 
				db.commit()

				st_markup = get_start_ui(message)

				bot.send_message(message.chat.id, "Администратор успешно добавлен!", reply_markup = st_markup)
			else:
				st_markup = get_start_ui(message)

				bot.send_message(message.chat.id, "Такой администратор уже существует!", reply_markup = st_markup)

@bot.message_handler(content_types = ['photo', 'video'])
def img_parser(message):
	sql.execute(f"SELECT is_running FROM admins WHERE is_running = 1")
	if sql.fetchone() is None:
		st_markup = get_start_ui(message)

		bot.send_message(message.chat.id, "Похоже, сессия не была запущена. Чтобы создать пост, сперва нужно запустить сессию.", 
			reply_markup = st_markup)
	else:
		react_markup = types.InlineKeyboardMarkup(row_width = 2)
		item1 = types.InlineKeyboardButton("👍", callback_data = 'like')
		item2 = types.InlineKeyboardButton("👎", callback_data = 'dislike')
		react_markup.add(item1, item2)

		#here should be also checked if sender started session or not

		session_user = sql.execute(f"SELECT username FROM admins WHERE is_running = 1")

		if(message.from_user.username = session_user):
			if(message.content_type == 'photo'):
				bot.send_message(message.chat.id, "Отлично, изображение принято!")
				bot.send_photo(config.CHANNEL, message.photo[-1].file_id, reply_markup = react_markup)
			else:
				bot.send_message(message.chat.id, "Отлично, видео принято!")
				bot.send_video(config.CHANNEL, message.video.file_id, reply_markup = react_markup)
		else:
			bot.send_message(message.chat.id, "❌Сессия была начата другим пользователем! Операция отклонена!❌")

@bot.callback_query_handler(func = lambda call: True)
def callback_inline(call):
	def check_id(call):
		response_dict = fb.get('/REACTIONS', '')

		if response_dict == None:
			post_data = Post(call.message.message_id, [], [])
			fb.post('/REACTIONS', json.loads(DataEncoder().encode(post_data)))
			check_id(call)
		else:
			id_found = False

			for key in response_dict.keys():
				if(response_dict[key]['post_id'] == call.message.message_id):
					list_likes = fb.get('/REACTIONS/' + key, 'liked_users')
					list_dis = fb.get('/REACTIONS/' + key, 'disliked_users')

					if call.data == 'like':
						if not call.from_user.username in response_dict[key]['liked_users'] and not call.from_user.username in response_dict[key]['disliked_users']:	
							list_likes.append(call.from_user.username)

							fb.put('/REACTIONS/' + key, '/liked_users', list_likes)
						elif not call.from_user.username in response_dict[key]['liked_users'] and call.from_user.username in response_dict[key]['disliked_users']:
							list_likes.append(call.from_user.username)
							list_dis.remove(call.from_user.username)

							fb.put('/REACTIONS/' + key, '/liked_users', list_likes)
							fb.put('/REACTIONS/' + key, '/disliked_users', list_dis)
						elif call.from_user.username in response_dict[key]['liked_users'] and not call.from_user.username in response_dict[key]['disliked_users']:
							list_likes.remove(call.from_user.username)

							fb.put('/REACTIONS/' + key, '/liked_users', list_likes)
					if call.data == 'dislike':
						if not call.from_user.username in response_dict[key]['liked_users'] and not call.from_user.username in response_dict[key]['disliked_users']:
							list_dis.append(call.from_user.username)

							fb.put('/REACTIONS/' + key, '/disliked_users', list_dis)
						elif call.from_user.username in response_dict[key]['liked_users'] and not call.from_user.username in response_dict[key]['disliked_users']:
							list_likes.remove(call.from_user.username)
							list_dis.append(call.from_user.username)

							fb.put('/REACTIONS/' + key, '/liked_users', list_likes)
							fb.put('/REACTIONS/' + key, '/disliked_users', list_dis)
						elif not call.from_user.username in response_dict[key]['liked_users'] and call.from_user.username in response_dict[key]['disliked_users']:
							list_dis.remove(call.from_user.username)

							fb.put('/REACTIONS/' + key, '/disliked_users', list_dis)

					likes = len(list_likes) - 1
					dislikes = len(list_dis) - 1

					new_markup = types.InlineKeyboardMarkup(row_width = 2)
					if likes != 0:
						item1 = types.InlineKeyboardButton("👍 " + str(likes), callback_data = 'like')
					else:
						item1 = types.InlineKeyboardButton("👍", callback_data = 'like')

					if dislikes != 0:
						item2 = types.InlineKeyboardButton("👎 " + str(dislikes), callback_data = 'dislike')
					else:
						item2 = types.InlineKeyboardButton("👎", callback_data = 'dislike')
					new_markup.add(item1, item2)

					bot.edit_message_reply_markup(chat_id = call.message.chat.id, message_id = call.message.message_id, reply_markup = new_markup)

					id_found = True
					
					break

			if not id_found:
				post_data = Post(call.message.message_id, ["#"], ["#"])
				fb.post('/REACTIONS', json.loads(DataEncoder().encode(post_data)))
				check_id(call)

	try:
		if call.message:
			if call.from_user.username != None:
				check_id(call)
			else:
				bot.answer_callback_query(callback_query_id=call.id, show_alert = True, text = "Вам нужно имя пользователя что бы оставлять реакции!")

	except Exception as e: 
		print(repr(e))

bot.polling(none_stop = True)
