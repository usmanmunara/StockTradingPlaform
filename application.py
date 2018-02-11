from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from datetime import datetime


from helpers import *

# configure the application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
   # select each symbol owned by the user and it's amount
    portfolio_symbols = db.execute("SELECT shares, symbol \
                                    FROM portfolio WHERE id = :id", \
                                    id=session["user_id"])

    # create a variable to store the Account Value ( remaining cash + share)
    account_value = 0

    # update each symbol prices and total
    for portfolio_symbol in portfolio_symbols:
        symbol = portfolio_symbol["symbol"]
        shares = portfolio_symbol["shares"]
        stock = lookup(symbol)
        total = shares * stock["price"]
        account_value += total
        db.execute("UPDATE portfolio SET price=:price, \
                    total=:total WHERE id=:id AND symbol=:symbol", \
                    price=usd(stock["price"]), \
                    total=usd(total), id=session["user_id"], symbol=symbol)

    # update user's cash in portfolio
    stock_cash = db.execute("SELECT cash FROM users \
                               WHERE id=:id", id=session["user_id"])

    # update account value with the value of the worth of shares
    account_value += stock_cash[0]["cash"]

    # print portfolio in index homepage
    updated_portfolio = db.execute("SELECT * from portfolio \
                                    WHERE id=:id", id=session["user_id"])

    return render_template("index.html", stocks=updated_portfolio, \
                            cash=usd(stock_cash[0]["cash"]), total= usd(account_value), )



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""


    if request.method == "GET":
        return render_template("buy.html")
    else:
        # ensure proper symbol
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("Invalid Symbol")

        # ensure that user requests for correct number of shares
        try:
            shares = int(request.form.get("shares"))
            if shares < 0:
                return apology("Amount of shares must be greater than 0")
        except:
            return apology("Amount of shares must be greater than 0")

        # Retrieve the cash a user has
        dollars = db.execute("SELECT cash FROM users WHERE id = :id", \
                            id=session["user_id"])

        # check if enough cash to buy
        if not dollars or float(dollars[0]["cash"]) < stock["price"] * shares:
            return apology("You cannot buy shares! Please add more cash")

        now = datetime.now()
        date_time = now.strftime("%Y-%m-%d %H:%M")


        # update history of shares bought
        db.execute("INSERT INTO history (symbol, shares, price, id, method, times, totaltrans) \
                    VALUES(:symbol, :shares, :price, :id, :method, :times, :totaltrans)", \
                    symbol=stock["symbol"], shares=shares, \
                    price=usd(stock["price"]), id=session["user_id"], method = "Buy", times= date_time, totaltrans = shares * stock["price"] )

        # update user cash
        db.execute("UPDATE users SET cash = cash - :purchase WHERE id = :id", \
                    id=session["user_id"], \
                    purchase=stock["price"] * float(shares))

        # Select user shares of that symbol
        user_shares = db.execute("SELECT shares FROM portfolio \
                           WHERE id = :id AND symbol=:symbol", \
                           id=session["user_id"], symbol=stock["symbol"])

        # if user doesn't has shares of that symbol, create new stock object
        if not user_shares:
            db.execute("INSERT INTO portfolio (id, name, shares, symbol, price, total) \
                        VALUES(:id, :name, :shares, :symbol, :price, :total)", \
                        id=session["user_id"] , name=stock["name"], \
                        shares=shares, symbol=stock["symbol"], price=usd(stock["price"]), \
                        total=usd(shares * stock["price"]))

        # Else increment the shares count
        else:
            shares_total = user_shares[0]["shares"] + shares
            db.execute("UPDATE portfolio SET shares=:shares \
                        WHERE id=:id AND symbol=:symbol", \
                        shares=shares_total, id=session["user_id"], \
                        symbol=stock["symbol"])

        # return to index
        return redirect(url_for("index"))

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    history = db.execute("SELECT * from history WHERE id=:id", id=session["user_id"])

    return render_template("history.html", history = history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        rows = lookup(request.form.get("symbol"))

        if not rows:
            return apology("Invalid Symbol")

        return render_template("quotation.html", stock=rows)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    request.form.get("name")
    """Register user."""

    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password")

        # ensure password and verified password is the same
        elif request.form.get("password") != request.form.get("passwordagain"):
            return apology("password doesn't match")

        # insert the new user into users, storing the hash of the user's password
        result = db.execute("INSERT INTO users (username, hash) \
                             VALUES(:username, :hash)", \
                             username=request.form.get("username"), \
                             hash=pwd_context.encrypt(request.form.get("password")))

        if not result:
            return apology("Username already exist")

        # remember which user has logged in
        session["user_id"] = result

        # redirect user to home page
        return redirect(url_for("index"))

    else:
        return render_template("register.html")
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""

    if request.method == "GET":
        return render_template("sell.html")
    else:
        # ensure proper symbol
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("Invalid Symbol")

        # ensure proper number of shares
        try:
            shares = int(request.form.get("shares"))
            if shares < 0:
                return apology("Amount of shares must be greater than 0")
        except:
            return apology("Amount of shares must be greater than 0")

        # select the symbol shares of that user
        user_shares = db.execute("SELECT shares FROM portfolio \
                                 WHERE id = :id AND symbol=:symbol", \
                                 id=session["user_id"], symbol=stock["symbol"])

        # check if enough shares to sell
        if not user_shares or int(user_shares[0]["shares"]) < shares:
            return apology("You don't hold enough shares")

        now = datetime.now()
        date_time = now.strftime("%Y-%m-%d %H:%M")

        # update history of a sell
        db.execute("INSERT INTO history (symbol, shares, price, id, method, times, totaltarns) \
                    VALUES(:symbol, :shares, :price, :id, :method, :times, :totaltrans)", \
                    symbol=stock["symbol"], shares=-shares, \
                    price=usd(stock["price"]), id=session["user_id"], method= "sell", times= date_time, totaltrans = shares * stock["price"])

        # update user cash (increase)
        db.execute("UPDATE users SET cash = cash + :purchase WHERE id = :id", \
                    id=session["user_id"], \
                    purchase=stock["price"] * float(shares))

        # decrement the shares count
        amountshares = user_shares[0]["shares"] - shares

        # if after decrement is zero, delete shares from portfolio
        if amountshares == 0:
            db.execute("DELETE FROM portfolio \
                        WHERE id=:id AND symbol=:symbol", \
                        id=session["user_id"], \
                        symbol=stock["symbol"])
        # otherwise, update portfolio shares count
        else:
            db.execute("UPDATE portfolio SET shares=:shares \
                    WHERE id=:id AND symbol=:symbol", \
                    shares=amountshares, id=session["user_id"], \
                    symbol=stock["symbol"])

        # return to index
        return redirect(url_for("index"))

@app.route("/watchlist", methods=["GET", "POST"])
@login_required
def watchlist():
    """Watchlist stocks."""

    if request.method == "POST":
        stock = lookup(request.form.get("symbol"))

        if not stock:
            return apology("Invalid Symbol")

        watchy = db.execute("SELECT symbol FROM watchlist \
                            WHERE symbol=:symbol", \
                            symbol=stock["symbol"])

        if watchy == stock["symbol"]:
            watchlist = db.execute("SELECT * from watchlist WHERE id=:id", id=session["user_id"])
            return render_template("watch.html", watchlist=watchlist)

        db.execute("INSERT INTO watchlist (symbol, price, id) \
                    VALUES(:symbol, :price, :id)", \
                    symbol=stock["symbol"] , \
                    price=usd(stock["price"]), id=session["user_id"])

        watchlist = db.execute("SELECT * from watchlist WHERE id=:id", id=session["user_id"])
        return render_template("watch.html", watchlist=watchlist)

    else:
        return render_template("watchlist.html")

