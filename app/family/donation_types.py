DONATION_TYPES = (
    {
        "code": "people_in_need",
        "label": "Donations to organizations helping people in need",
        "tax_reduction": "75%",
        "tax_return_box": "7UD",
        "ceiling": 1000,
    },
    {
        "code": "public_interest",
        "label": "Donations to other public-interest organizations",
        "tax_reduction": "66%",
        "tax_return_box": "7UF",
        "ceiling": 0,
    },
    {
        "code": "religious_heritage",
        "label": "Donations for the preservation of religious heritage",
        "tax_reduction": "75%",
        "tax_return_box": "7UJ",
        "ceiling": 1000,
    },
    {
        "code": "european_people_in_need",
        "label": "Donations to organizations helping people in need established in another European country",
        "tax_reduction": "75%",
        "tax_return_box": "7VA",
        "ceiling": 1000,
    },
    {
        "code": "european_public_interest",
        "label": "Donations to public-interest organizations established in another European country",
        "tax_reduction": "66%",
        "tax_return_box": "7VC",
        "ceiling": 0,
    },
    {
        "code": "political_party",
        "label": "Political party donations and membership contributions",
        "tax_reduction": "66%",
        "tax_return_box": "7UH",
        "ceiling": 7500,
    },
    {
        "code": "election_campaign",
        "label": "Donations to finance an election candidate's campaign",
        "tax_reduction": "66%",
        "tax_return_box": "7UF",
        "ceiling": 0,
    },
)

DONATION_TYPE_CODES = tuple(donation_type["code"] for donation_type in DONATION_TYPES)
DONATION_TYPES_BY_CODE = {donation_type["code"]: donation_type for donation_type in DONATION_TYPES}
