from config_secrets import TOKEN, pg_pwd, csrf_secret, session_key, ratelimit_bypass_key, oauth_client_secret

site = "" # Replace this with your domain
site_errors_channel = 815055552857243699 # Where to log site errors
main_server=789934742128558080 # Main server

class OauthConfig:
    client_id = "726157768385363978"
    client_secret = oauth_client_secret
    scope = ["identify"]
    redirect_uri = "https://" + site + "/auth/login/confirm"
owner = 563808552288780322
# Confusing right? Sorry, i already did 50% using reviewing server so meow ig
staff_roles = {
    "guild": {
        "id": 00000000000000000,
        "perm": 1
    },
    "bot_review": {
        "id": 789941907563216897,
        "perm": 2
    },
    "mod": {
        "id": 789935016690843708,
        "perm": 3
    },
    "admin": {
        "id": 789935015131742228,
        "perm": 4,
    },
    "owner": {
        "id": 789935014275317780,
        "perm": 5,
    }
}

pg_user = 'rootspring'

# This value below dont need to be changed
site_url = "https://" + site

supported_fields_posting = ("server_count", "shard_count", "shards", "shard_id")
supported_fields_guv = ('user_id', 'res_voted')
