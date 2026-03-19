class PolicyEngine:
    def __init__(self):
        self.rules = []

    def add_rule(self, rule):
        self.rules.append(rule)

    def validate(self, request):
        for rule in self.rules:
            if not rule(request):
                raise Exception("Policy violation")
        return True


def no_phi_rule(data):
    return "SSN" not in data
