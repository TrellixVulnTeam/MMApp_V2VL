import os 
import pandas as pd
import datetime
import random
import json
import sqlite3
from credentials import end_point_address, encryption, create_keys_rsa, encrypt_packet, decrypt_packet


import kivy
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.network.urlrequest import UrlRequest 
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.bubble import BubbleButton
from kivy.app import App


kivy.require('2.0.0')


class User():
    def __init__(self, user_id, phone_number, email, username):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.phone_number = phone_number
        self.password = None
        self.add_new_transaction_dict = None
        self.delete_transaction_dict = None
        self.freq_map = {
            "Once": 1,
            "Daily": 1000,
            "Weekly": 7,
            "Bi-Weekly": 14,
            "Monthly": 30,
            "Quarterly": 90,
            "Annually": 360
        }

         
    def __repr__(self):
        self.dataframe = pd.DataFrame({
            "user_id": [self.user_id],
            "username": [self.username],
            "user_email": [self.email], 
            "phone_number": [self.phone_number]
        })
        return str(self.dataframe)
    def write_self(self):
        self.dataframe = pd.DataFrame({
            "user_id": [self.user_id],
            "username": [self.username],
            "user_email": [self.email], 
            "phone_number": [self.phone_number]
        })
        conn = sqlite3.connect("user.db")
        self.dataframe.to_sql("user_table", if_exists='replace', con=conn)
        
class Screen(Screen):
    def __init__(self, name):
        self.previous_screen = None
        self.next_screen = None
        self.today = None
        super().__init__()
        self.name = name
        self.translate_columns = {
            "ID":"transaction_id",
            "Date":"transaction_date",
            "Amount":"amount",
            "Loc":"location",
            "Type":"transaction_type",
            "Tag":"transaction_tag",
            "Wallet":"wallet_name"
        }
        self.calender= {
            "1": "Jan",
            "2": "Feb",
            "3": "Mar",
            "4": "Apr",
            "5": "May",
            "6": "Jun",
            "7": "Jul",
            "8": "Aug",
            "9": "Sep",
            "10": "Oct",
            "11": "Nov",
            "12": "Dec"
        }
        self.ordered_weekdays = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
       
    def __repr__(self):
        return f"previous Screen: {self.previous_screen}\nnext Screen: {self.next_screen}\nScreen Name:{self.name}\nsend_request commands:\n\t'register user'\n\t'login'\n\t'update'"
    
    def screen_transition(self, screen, direction='left', duration=1):
        self.manager.transition.direction = direction
        self.manager.transition.duration = duration
        self.manager.current = screen
    
    def load_transaction(self, button):
        self.manager.get_screen("ViewTransactionScreen").previous_screen = self.name
        self.screen_transition("ViewTransactionScreen", direction='up')
        self.manager.get_screen("ViewTransactionScreen").populate_screen(button.text)
  
    def send_request(self, data, action):
        endpoints = {
            "register user":"register_user",
            "login": "login_user",
            "update":"user_services/update",
        }

        UrlRequest(
            f"https://{end_point_address}/{endpoints[action]}", 
            req_headers={'Content-type': 'application/json', "fromApp": "True"}, 
            req_body=data,
            on_success=self.request_response, 
            on_progress=self.animation, 
            timeout=20, 
            on_error=self.request_error, 
            on_failure=lambda x,y: print("failure",y), 
            verify=False
        )
    
    def request_response(self, req, response):
        response = json.loads(response)        
        if "Success" in response.keys():
            if response["Success"] == 'registration complete':
                #register user
                global app_user
                data = decrypt_packet(response)
                app_user.user_id = data["id"]
                #save keys
                with open(f"{app_user.username}_privkey", "w") as f:
                    f.write(data['privkey'])
                with open(f"{app_user.username}_pubkey", "w") as f:
                    f.write(response['pubkey'])
                for w in self.ids.values():
                    w.text = ""
                #transition to loginscreen
                self.screen_transition("LoginScreen")
                #write to database
                app_user.write_self()
            elif response["Success"] == "User logged in with ID and password":
                #retrieve tables from end point and save to app_user
                packet = decrypt_packet(response, user=app_user.username)
                app_user.transactions = pd.DataFrame.from_dict(json.loads(packet["Transactions"]))
                app_user.schedule = pd.DataFrame.from_dict(json.loads(packet["Schedule"]))
                app_user.goals = pd.DataFrame.from_dict(json.loads(packet["Goals"]))
                app_user.wallets = pd.DataFrame.from_dict(json.loads(packet["Wallets"]))
                app_user.budgets =  pd.DataFrame.from_dict(json.loads(packet["Budgets"]))
                #transition to main menu
                self.screen_transition("MenuScreen")
            elif response["Success"] == "Transaction added":
                transaction_id = len(app_user.transactions.transaction_id) 
                transaction_df = pd.DataFrame({
                    "transaction_id": [int(transaction_id)],
                    "transaction_date": [app_user.add_new_transaction_dict["calender"]],
                    "amount": [float(app_user.add_new_transaction_dict["amount"])],
                    "location": [app_user.add_new_transaction_dict["location"]],
                    "transaction_type": [app_user.add_new_transaction_dict["transaction_type"]],
                    "transaction_tag": [app_user.add_new_transaction_dict["tag"]],
                    "wallet_name": [app_user.add_new_transaction_dict["wallet"]]
                })
                #add to transaction table
                app_user.transactions = pd.concat([app_user.transactions, transaction_df])
                app_user.transactions.transaction_id = app_user.transactions.transaction_id.astype('int')
                app_user.transactions.reset_index(inplace=True, drop=True)
                #check if transaction is scheduled for today
                if app_user.add_new_transaction_dict["calender"] == str(datetime.datetime.today().date()):
                    #subtract from wallet
                    if app_user.add_new_transaction_dict["transaction_type"] == "Withdrawl":
                        app_user.wallets.loc[app_user.wallets.wallet_name == app_user.add_new_transaction_dict["wallet"], "wallet_amount"] -= float(app_user.add_new_transaction_dict["amount"])
                    #add to wallet
                    elif app_user.add_new_transaction_dict["transaction_type"] == "Deposit":
                        app_user.wallets.loc[app_user.wallets.wallet_name == app_user.add_new_transaction_dict["wallet"], "wallet_amount"] += float(app_user.add_new_transaction_dict["amount"])
                #schedule the transaction
                if app_user.add_new_transaction_dict["frequency"] != "Daily" and app_user.add_new_transaction_dict["calender"] != str(datetime.datetime.today().date()):
                    schedule_df = pd.DataFrame({
                        "transaction_id": [int(transaction_id)],
                        "frequency": [app_user.freq_map[app_user.add_new_transaction_dict['frequency']]],
                        "scheduled_date": [app_user.add_new_transaction_dict["calender"]],
                        "next_day": [datetime.datetime.strptime(app_user.add_new_transaction_dict["calender"], "%Y-%m-%d") + datetime.timedelta(days=app_user.freq_map[app_user.add_new_transaction_dict['frequency']])],
                        "amount": [app_user.add_new_transaction_dict["amount"]],
                        "transaction_type": [app_user.add_new_transaction_dict["transaction_type"]],
                        "wallet_name": [app_user.add_new_transaction_dict["wallet"]],
                        "added_today": [True]
                    })
                    app_user.schedule = pd.concat([app_user.schedule, schedule_df])
                    app_user.transactions.reset_index(inplace=True, drop=True)
                    app_user.schedule.transaction_id = app_user.schedule.transaction_id.astype('int')
                    app_user.schedule.frequency = app_user.schedule.frequency.astype('int')
                for i,v in self.ids.items():
                    if i != "transaction_type" and i != "dropdown" and i != "wallet_dropdown" and i != "frequency_dropdown" and i != "back_button":
                        v.text = ""
                        self.ids["calender"].text = "calender"
                self.prompt("Success","Transaction Added")
                
            elif response["Success"] == "Transaction deleted and Wallet updated":
                #drop row from dataframe
                app_user.transactions.drop(app_user.transactions.loc[app_user.transactions.transaction_id == int(app_user.delete_transaction_dict["transaction_id"])].index, inplace=True)
                #decrement all ids greater than current by 1
                app_user.transactions.loc[app_user.transactions.transaction_id > int(app_user.delete_transaction_dict["transaction_id"]), "transaction_id"] -= 1
                #return reverse transaction from wallet
                if app_user.delete_transaction_dict["transaction_type"] == "Withdrawl":
                    #if withdrawl deleted return the amount to the wallet
                    app_user.wallets.loc[app_user.wallets.wallet_name == app_user.delete_transaction_dict["wallet_name"], "wallet_amount"] += float(app_user.delete_transaction_dict["amount"])
                elif app_user.delete_transaction_dict["transaction_type"] == "Deposit":
                    #if deposit deleted subtract amount from wallet
                    app_user.wallets.loc[app_user.wallets.wallet_name == app_user.delete_transaction_dict["wallet_name"], "wallet_amount"] += float(app_user.delete_transaction_dict["amount"])
                
                if  int(app_user.delete_transaction_dict["transaction_id"]) in app_user.schedule.transaction_id.tolist():
                    app_user.schedule.drop(app.schedule.loc[app_user.schedule.transaction_id == int(app_user.delete_transaction_dict["transaction_id"])].index, inplace=True)
                #clear screen
                for widget in self.ids.values():
                    widget.text = ""
                self.prompt("Success", response["Success"])


                
        else:
            self.prompt("Error", response["Error"])
    
    def request_error(self, req, error):
        print("error")
        self.prompt(f"{self.name}Error",error)
        
    def prompt(self, error_type, error_message):
        cb = BubbleButton(text=f"{error_message}\n\n\n\n   Close")
        pu = Popup(title=f"{error_type}", content=cb, size_hint=(.5, .5))
        cb.bind(on_press=pu.dismiss)
        pu.open()
    
    def check_user_inputs(self, inputs, registration=False):
        if registration == True:
            if len(inputs["password"]) < 8:
                self.prompt("InputError", "Password Must be at least 8 characters long")
                return False
            elif inputs["confirmation"] != inputs["password"]:
                self.prompt("InputError", "Passwords must match")
                return False
            else:
                pass
        
        for i,v in inputs.items():
            if ";" in v or "select" in v.lower() or "drop" in v.lower():
                self.prompt("InputError", "No input can hold the character ';', word 'SELECT' or 'DROP'")
                return False
        
        return True
    
    def build_calender(self, year=datetime.datetime.now().year, month=datetime.datetime.now().month, mini=False):
        days_in_month = self.collect_days_in_month(year, month)
        self.ids['year_label'].text = str(year)
        self.ids['current_month'].text = self.calender[str(month)]
        #create a dictionary for calender weekdays related to current month
        dict_calender={}
        for i in range(1,8):
            dict_calender[f'{["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][datetime.date(year, month, i).weekday()]}'] = []
        #pair related dates to related weekdays
        for i,v in zip(list(dict_calender.keys()) * (days_in_month//len(dict_calender.keys()) + 1) , [x for x in range(1,days_in_month+1)]):
            dict_calender[i].append(v)
        #find the first of the month
        first_of_month = [i for i,v in dict_calender.items() if 1 in v][0]
        #add padding (empty cells) before the first of the month
        for i in self.ordered_weekdays:
            if i == first_of_month:
                break
            dict_calender[i] = [""] + dict_calender[i]
        #add padding (empty cells) to the last day of the month
        max_len = max([len(i) for i in dict_calender.values()])
        for v in dict_calender.values():
            while len(v) != max_len:
                v.append("")
        #create a dataframe        
        calender_df = pd.DataFrame(dict_calender)
        #order weekdays
        calender_df = calender_df[["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]]
        #iterate over dataframe and add to gridlayout widget
        for column in calender_df.columns:
            self.ids['gl_calender'].add_widget(Label(text=column))
        for row in calender_df.values:
            for cell in row:
                #padding months and days
                if len(str(cell)) == 1:
                    new_cell = f"0{cell}"
                else:
                    new_cell = cell
                if len(str(month)) == 1:
                    month = f"0{month}"
                else:
                    month = month
                
                if f"{year}-{month}-{new_cell}" in list(app_user.schedule["scheduled_date"]) and f"{year}-{month}-{new_cell}" != str(datetime.datetime.now().date()):
                    if mini == True:
                        bb = BubbleButton(text=f"{cell}", on_press=self.select_day)
                    else:
                        bb = BubbleButton(text=f"{cell}", on_press=self.view_day)
                    bb.background_normal = ""
                    bb.background_color=  (.4, .5, 100, .3)
                    self.ids['gl'].add_widget(bb)
                    continue

                if f"{year}-{month}-{new_cell}" == str(datetime.datetime.now().date()):
                    if mini == True:
                        bb = BubbleButton(text=f"Today {cell}", on_press=self.select_day)
                    else:
                        bb = BubbleButton(text=f"Today {cell}", on_press=self.view_day)
                    bb.background_normal = ""
                    bb.background_color = (0, .5, 1, .5)
                    self.ids['gl_calender'].add_widget(bb)                           

                elif cell == "":
                    self.ids['gl_calender'].add_widget(Label(text=""))
                
                else:
                    if mini == True:
                        bb = BubbleButton(text=f"{cell}", on_press=self.select_day)
                    else:
                        bb = BubbleButton(text=f"{cell}", on_press=self.view_day)
                    bb.halign = "center"
                    bb.valign = "middle"
                    bb.text_size = (20,20)
                    self.ids['gl_calender'].add_widget(bb)
        self.selected_month = int(month)
    
    def view_day(self, button):
        if "Today" in button.text:
            today = button.text.replace("Today ","")
        else:
            today = button.text
        self.manager.get_screen("DayScreen").load_day(self.ids["year_label"].text, self.selected_month, today)
        self.screen_transition("DayScreen")

    def select_day(self, button):
        print(self.parent.parent.parent.parent.parent)
        self.manager.get_screen("AddTransactionScreen").ids["calender"].text = button.text

    def change_month(self, button):
        current_month = int([i for i,v in self.calender.items() if v == self.ids["current_month"].text][0])
        if button.text == "<":
            #logic to decrement month based on january
            if current_month == 1:
                current_month = 12
                self.ids["year_label"].text = str(int(self.ids["year_label"].text) - 1)
                self.ids["current_month"].text = self.calender["12"]
            else:
                current_month -= 1
                self.ids["current_month"].text = self.calender[str(current_month)]
        #logic to increment month
        elif button.text == ">":
            #logic to increment based on december
            if current_month == 12:
                current_month = 1
                self.ids["year_label"].text = str(int(self.ids["year_label"].text) + 1)
                self.ids["current_month"].text = self.calender[str(current_month)]                
            else:
                current_month += 1
                self.ids["current_month"].text = self.calender[str(current_month)]
        self.selected_month = current_month
        #clear the calender
        self.clear_calender()
        #load the new months data
        self.build_calender(int(self.ids["year_label"].text), current_month)
    
    def clear_calender(self):
        self.ids['gl_calender'].clear_widgets()
    
    def collect_days_in_month(self, year, month):
        #calculate days in month based on december month
        if month == 12:
            days_in_month = (datetime.date(year, 2, 1) - datetime.date(year, 1, 1)).days
        #calculate days in month based on january month
        elif month == 1:
            days_in_month = (datetime.date(year + 1, 1, 1) - datetime.date(year, 12, 1)).days
        #calculate days in month based on month
        else:
            days_in_month = (datetime.date(year, month + 1, 1) - datetime.date(year, month, 1)).days
        return days_in_month

    def animation(self, req, start, end):
        print(start, end)
        pass
        
class RegistrationScreen(Screen):
    def register(self):
        user_inputs = {i:v.text for i,v in self.ids.items()}
        if self.check_user_inputs(user_inputs, registration=True) == True:
            global app_user
            app_user = User("None", user_inputs["phone_number"], user_inputs["email"], user_inputs["username"])
            packet = encryption(json.dumps(user_inputs))
            self.send_request(packet, "register user")

        else:
            return
        
class LoginScreen(Screen):
    def login(self):
        user_inputs = {i:v.text for i,v in self.ids.items()}
        packet = user_inputs.copy()
        if self.check_user_inputs(user_inputs) == True:
            global app_user
            df = pd.read_sql(f"SELECT * FROM user_table", con=sqlite3.connect("user.db"))
            app_user = User(df.user_id.item(), df.phone_number.item(), df.user_email.item(), df.username.item())
            app_user.password = user_inputs["password"]
            packet = encrypt_packet(packet, user=app_user.username)
            packet["USER"] = app_user.username
            packet["USERID"] = app_user.user_id
            self.send_request(json.dumps(packet), "login")

class MenuScreen(Screen):
    def log_out(self):
        global app_user
        del app_user
        self.screen_transition("LoginScreen", direction='right')

class TransactionsScreen(Screen):
    def display_transactions(self):
        self.column_states = {i: "unsorted" for i in self.translate_columns.keys()}
        #load the GridLayout object
        gl = self.ids["gl"] 
        #clear the widgets on gl in case there are any currently existing
        gl.clear_widgets()
        gl.size_hint_y = len(app_user.transactions) / 2.5
        #iterate over the transactions dataframe and add values to the kivy Gridlayout object
        for row in app_user.transactions.values:
            gl.add_widget(BubbleButton(text=str(row[0]), on_press=self.load_transaction, background_normal="", background_color=(.4, .5, 100, .3)))
            for cell in row[1:]:
                gl.add_widget(Label(text=str(cell)))
    
    def sort_transactions(self, button):
        #clear the current widgets on gl
        gl = self.ids["gl"] 
        gl.clear_widgets()
        gl.size_hint_y = len(app.transactions) / 2.5
        if self.column_states[button.text] == "unsorted":
            for row in self.transactions.sort_values(self.translate_columns[button.text], ascending=True).values:
                gl.add_widget(BubbleButton(text=str(row[0]), on_press=self.load_transaction, background_normal="", background_color=(.4, .5, 100, .3)))
                for cell in row[1:]:
                    gl.add_widget(Label(text=str(cell)))
            self.column_states[button.text] = "sorted"
            return
        elif self.column_states[button.text] == "sorted":
            for row in self.transactions.sort_values(self.translate_columns[button.text], ascending=False).values:
                gl.add_widget(BubbleButton(text=str(row[0]), on_press=self.load_transaction, background_normal="", background_color=(.4, .5, 100, .3)))
                for cell in row[1:]:
                    gl.add_widget(Label(text=str(cell)))
            self.column_states[button.text] = "unsorted"
            return

class AddTransactionScreen(Screen):
        def build_screen(self, date=datetime.datetime.now().date()):
            self.ids["calender"].text = f"{date}"
            wd = self.ids["wallet_dropdown"]
            wd.clear_widgets()
            for i in app_user.wallets["wallet_name"].tolist():
                wd.add_widget(Button(text=f"{i}", size_hint_y=None, on_press= lambda x: wd.select(x.text)))
        def add_transaction(self):
            user_inputs = {i:v.text for i,v in self.ids.items() if i != "dropdown" and i != "wallet_dropdown" and i != "frequency_dropdown"}
            if self.check_user_inputs(user_inputs) == True:
                #build packet
                user_inputs["user_id"] = app_user.user_id
                user_inputs["user_password"] = app_user.password
                packet = user_inputs.copy()
                #encrypt packet
                packet = encrypt_packet(packet, user=app_user.username)
                packet["update"] = "add transaction"
                packet["user_name"] = app_user.username
                #create transaction dictionary 
                app_user.add_new_transaction_dict = user_inputs
                self.send_request(json.dumps(packet), "update")
        def mini_calender(self):
            sc = ScheduleScreen("MiniCalender")
            sc.build_calender(mini=True)
            pu = Popup(title="Calender", content=sc, size_hint=(.7, .7))
            self.pu = pu
            #bb = BubbleButton(text="Close", on_press=self.pu.dismiss)
            #sc.ids["bl"].remove_widget(sc.ids["dynamic_button"])
            #sc.ids["bl"].add_widget(bb)
            self.pu.open()
                
class ViewTransactionScreen(Screen):
    def populate_screen(self, button_txt):
        self.transaction_id = int(button_txt)
        transaction_df = app_user.transactions.loc[app_user.transactions.transaction_id == self.transaction_id]
        self.ids["transaction_id"].text = str(transaction_df.transaction_id.item())
        self.ids["date"].text = str(transaction_df.transaction_date.item())
        self.ids["amount"].text = str(transaction_df.amount.item())
        self.ids["location"].text = str(transaction_df.location.item())
        self.ids["type"].text = str(transaction_df.transaction_type.item())
        self.ids["tag"].text = str(transaction_df.transaction_tag.item())
        self.ids["wallet"].text = str(transaction_df.wallet_name.item())
    def delete_transaction(self):
        data = {
            "transaction_id": self.ids["transaction_id"].text,
            "wallet_name": self.ids["wallet"].text,
            "amount": self.ids["amount"].text,
            "user_id": str(app_user.user_id),
            "user_password": str(app_user.password),
            "transaction_type": self.ids["type"].text
        }
        #create a copy of the data
        packet = data.copy()
        #send encrypted packet
        packet = encrypt_packet(packet, user=app_user.username)
        packet["user_name"] = app_user.username
        packet["update"] = "delete transaction"
        app_user.delete_transaction_dict = data
        self.send_request(json.dumps(packet), "update")

class ScheduleScreen(Screen):
    pass

class DayScreen(Screen):
    def load_day(self, year, month, day):
        if len(str(month)) == 1:
            month = f"0{month}"
        if len(str(day)) == 1:
            day = f"0{day}"
        self.ids["date"].text = f"{year}-{month}-{day}"
        gl = self.ids["gl"]
        day_data = app_user.schedule.loc[app_user.schedule.scheduled_date == f"{year}-{month}-{day}"]
        gl.clear_widgets()
        for row in day_data[["transaction_id", "frequency", "scheduled_date","transaction_type", "amount", "wallet_name"]].values:
            gl.add_widget(BubbleButton(text=str(row[0]), background_normal="", background_color=(.4, .5, 100, .3), on_press=self.find_transaction))
            for item in row[1:]:
                gl.add_widget(Label(text=str(item)))
    def add_transaction(self):
        self.manager.get_screen("AddTransactionScreen").previous_screen = self.name
        self.manager.get_screen("AddTransactionScreen").build_screen(date=self.ids["date"].text)
        self.screen_transition("AddTransactionScreen")
    

class MonManApp(App):
    def build(self):
        self.sm = ScreenManager()
        self.sm.add_widget(RegistrationScreen(name="RegistrationScreen"))
        self.sm.add_widget(LoginScreen(name="LoginScreen"))
        self.sm.add_widget(MenuScreen(name="MenuScreen"))
        self.sm.add_widget(TransactionsScreen(name="TransactionsScreen"))
        self.sm.add_widget(AddTransactionScreen(name="AddTransactionScreen"))
        self.sm.add_widget(ViewTransactionScreen(name="ViewTransactionScreen"))
        self.sm.add_widget(ScheduleScreen(name="ScheduleScreen"))
        self.sm.add_widget(DayScreen(name="DayScreen"))
        if "user.db" in os.listdir():
            self.sm.current =  "LoginScreen"
        else:
            self.sm.current = "RegistrationScreen"
        return self.sm

if __name__ ==  "__main__":
    MonManApp().run()