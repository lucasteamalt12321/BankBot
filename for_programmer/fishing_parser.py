from telebot import Message

message:Message # любое сообщение, которое видит бот
text=message.text

if "🎣 [Рыбалка] 🎣" in text:
    lines=message.splitlines()
    for line in lines:
        if "Рыбак" in line:
            _, fisher = line.split(":")
        if "Монеты" in line:
            _,a=line.split("+")
            coins,_=a.split("(")

