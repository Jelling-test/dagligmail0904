try:
    import app
    print("App blev importeret uden fejl")
except Exception as e:
    import traceback
    with open("error_log.txt", "w") as f:
        f.write(traceback.format_exc())
    print("Fejl fanget og skrevet til error_log.txt")
