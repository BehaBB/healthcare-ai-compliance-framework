import yaml

class YAMLPolicyEngine:
    def __init__(self, path):
        with open(path, "r") as f:
            self.config = yaml.safe_load(f)

    def validate(self, text):
        for rule in self.config["rules"]:
            if rule["type"] == "keyword_block":
                for word in rule["keywords"]:
                    if word.lower() in text.lower():
                        raise Exception(f"Blocked keyword: {word}")
        return True
