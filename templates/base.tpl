<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" type="text/css" href="/static/libs/bulma.min.css">
    <link rel="stylesheet" type="text/css" href="/static/main.css">
    {% include "partials/fonts.tpl" %}
</head>
<body>
    {% block content %}{% endblock %}
    <script type="text/javascript" src="/static/libs/vue.min.js"></script>
    <script type="text/javascript" src="/static/index.js"></script>
</body>
</html>