IFU_FIELD_GROUPS = (
    {
        "title": "Interests and dividends",
        "fields": (
            {"key": "box_2tr", "code": "2TR", "label": "Interest and other fixed-income investment income"},
            {"key": "box_2tt", "code": "2TT", "label": "Interest from participatory loans and minibonds"},
            {"key": "box_2dc", "code": "2DC", "label": "Share and unit income eligible for the 40% allowance when the progressive tax scale is selected"},
        ),
    },
    {
        "title": "Withholding tax and social contributions",
        "fields": (
            {"key": "box_2cg", "code": "2CG", "label": "Income already subject to social contributions, without deductible CSG"},
            {"key": "box_2bh", "code": "2BH", "label": "Income already subject to social contributions, with deductible CSG when the progressive tax scale is selected"},
            {"key": "box_2ck", "code": "2CK", "label": "Non-final flat-rate withholding tax already paid"},
            {"key": "box_2df", "code": "2DF", "label": "Other income already subject to social contributions, with deductible CSG"},
        ),
    },
    {
        "title": "Life insurance and capitalization contracts",
        "fields": (
            {"key": "box_2dh", "code": "2DH", "label": "Life-insurance and capitalization-contract proceeds subject to 7.5% final withholding tax"},
            {"key": "box_2yy", "code": "2YY", "label": "Other proceeds from life-insurance and capitalization contracts of less than eight years, for contributions made before 27 September 2017"},
            {"key": "box_2zz", "code": "2ZZ", "label": "Proceeds from life-insurance and capitalization contracts of less than eight years, for contributions made from 27 September 2017"},
        ),
    },
)

IFU_FIELD_KEYS = tuple(field["key"] for group in IFU_FIELD_GROUPS for field in group["fields"])
