from app import create_app

application = create_app(config_name='production')

if __name__ == "__main__":
    application.run()