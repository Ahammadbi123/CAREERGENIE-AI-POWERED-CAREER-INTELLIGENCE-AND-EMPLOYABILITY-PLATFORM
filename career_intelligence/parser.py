# parser.py

def load_simulated_dataset():
    """
    Generates simulated realistic job description dataset
    based on real hiring trends of top 10 companies.
    """

    dataset = [
        {
            "company": "Amazon",
            "type": "Product",
            "description": """
            Strong Data Structures and Algorithms required.
            Experience in Java or Python.
            AWS cloud knowledge preferred.
            Problem solving and system design skills required.
            """
        },
        {
            "company": "Google",
            "type": "Product",
            "description": """
            Excellent problem solving and algorithmic thinking.
            Strong knowledge of C++, Java or Python.
            System design and scalability experience.
            OOPS fundamentals required.
            """
        },
        {
            "company": "Microsoft",
            "type": "Product",
            "description": """
            Experience in C#, Java, or Python.
            Strong OOPS and system design.
            Cloud knowledge (Azure preferred).
            Good communication and teamwork.
            """
        },
        {
            "company": "Infosys",
            "type": "Service",
            "description": """
            Basic programming in Java or Python.
            Good communication skills.
            Knowledge of SQL and DBMS.
            Strong learning ability.
            """
        },
        {
            "company": "TCS",
            "type": "Service",
            "description": """
            Programming fundamentals required.
            OOPS and SQL knowledge.
            Good communication and teamwork.
            Adaptability and client interaction skills.
            """
        },
        {
            "company": "Wipro",
            "type": "Service",
            "description": """
            Java, Python knowledge.
            SQL and DBMS.
            Communication skills.
            Problem solving and flexibility.
            """
        },
        {
            "company": "Flipkart",
            "type": "Product",
            "description": """
            Strong Data Structures and Algorithms.
            Java backend systems.
            Microservices and scalability.
            AWS and cloud infrastructure.
            """
        },
        {
            "company": "Accenture",
            "type": "Service",
            "description": """
            Programming fundamentals.
            SQL and cloud exposure.
            Client delivery experience.
            Communication and teamwork.
            """
        },
        {
            "company": "Meta",
            "type": "Product",
            "description": """
            Strong C++ or Python.
            Algorithms and system design.
            Scalable distributed systems.
            Problem solving excellence.
            """
        },
        {
            "company": "IBM",
            "type": "Service",
            "description": """
            Java, Python programming.
            Cloud (IBM Cloud/AWS).
            SQL and DBMS.
            Communication skills.
            """
        }
    ]

    return dataset