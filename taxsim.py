from easyfrenchtax import TaxSimulator

def simulateTax(elements):
    income = elements["Income"]
    charity = elements["Charity"]
    tax_input = {
        "household_shares": 2,
        "nb_kids": 0,
        "salary_1_1AJ": income.income_1 if income else 0,
        "salary_2_1BJ": income.income_2 if income else 0,
        "charity_donation_7UD": charity.charity_7UD if charity else 0,
        "charity_donation_7UF": charity.charity_7UF if charity else 0
    }
    tax_result = TaxSimulator(tax_input).state
    return tax_result["net_taxes"]