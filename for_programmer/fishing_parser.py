from telebot import Message

message:Message # любое сообщение, которое видит бот
text=message.text  # noqa: F821 - фрагмент-заготовка

if "🎣 [Рыбалка] 🎣" in text:
    lines=text.splitlines()
    for line in lines:
        if "Рыбак" in line:
            _, fisher = line.split(":")
        if "Монеты" in line:
            _,a=line.split("+")
            coins,_=a.split("(")

