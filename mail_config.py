from flask_mail import Mail, Message

mail = Mail()

def init_mail(app):
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = app.config.get('MAIL_USERNAME', 'your-email@gmail.com')
    app.config['MAIL_PASSWORD'] = app.config.get('MAIL_PASSWORD', 'your-app-password')
    app.config['MAIL_DEFAULT_SENDER'] = app.config.get('MAIL_USERNAME', 'your-email@gmail.com')
    
    mail.init_app(app)
    return mail

def send_notification(subject, recipient, body):
    try:
        msg = Message(
            subject=subject,
            recipients=[recipient],
            body=body
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False 