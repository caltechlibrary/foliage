<!doctype html>
<html lang="">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>{{ title }}</title>
    <meta name="description" content="{{ description }}">
    <link rel="stylesheet" href="{{ base_url }}css/markdown.min.css">
    {% if bootstrap_css %}
    <link rel="stylesheet" href="{{ bootstrap_css }}">
    {% else %}
    <link rel="stylesheet" href="{{ base_url }}css/bootstrap.min.css">
    {% end %}
    <link rel="stylesheet" href="{{ base_url }}css/toastify.min.css">
    <link rel="stylesheet" href="{{ base_url }}css/app.css">
    {% for css in css_file %}
        {% if css %}<link rel="stylesheet" href="{{ css }}">{% end %}
    {% end %}
    {% if css_style %}
    <style>{% raw css_style %}</style>
    {% end %}
</head>
<body>
<div class="pywebio">
    <div class="container no-fix-height" id="output-container">
        <div class="markdown-body" id="markdown-body">
            <div class="text-center" id="pywebio-loading"
                 style="display: none; position: fixed; top: 40%; left: 0;right: 0;">
                <div class="spinner-grow text-info" role="status">
                    <span class="sr-only">Loading...</span>
                </div>
            </div>

            <div id="pywebio-scope-ROOT">{% raw content %}</div>
        </div>
        <div id="end-space"></div>

    </div>

    <div id="input-container">
        <div id="input-cards" class="container"></div>
    </div>
</div>

<footer class="footer">
</footer>

<script src="{{ base_url }}js/mustache.min.js"></script>  <!--template system-->
<script src="{{ base_url }}js/prism.min.js"></script>  <!-- markdown code highlight -->
<script src="{{ base_url }}js/FileSaver.min.js"></script>  <!-- saving files on the client-side -->
<script src="{{ base_url }}js/jquery.min.js"></script>
<script src="{{ base_url }}js/popper.min.js"></script>  <!-- tooltip engine -->
<script src="{{ base_url }}js/bootstrap.min.js"></script>
<script src="{{ base_url }}js/toastify.min.js"></script> <!-- toast -->
<script src="{{ base_url }}js/bs-custom-file-input.min.js"></script> <!-- bootstrap custom file input-->
<script src="{{ base_url }}js/purify.min.js"></script>  <!-- XSS sanitizer -->
<script>
    if (window.navigator.userAgent.indexOf('MSIE ') !== -1 || window.navigator.userAgent.indexOf('Trident/') !== -1)
        $('#output-container').html('<div class="alert alert-danger" role="alert"> Sorry, this website does not support IE browser.</div>');
</script>
<script src="{{ base_url }}js/pywebio.min.js"></script>

<script src="{{ base_url }}js/require.min.js"></script> <!-- JS module loader -->
{% for js in js_file %}
    {% if js %}<script src="{{ js }}"></script>{% end %}
{% end %}
{% if script %}
<script>
    $(function () {
        // https://www.npmjs.com/package/bs-custom-file-input
        bsCustomFileInput.init()
    });

    const urlparams = new URLSearchParams(window.location.search);
    WebIO.startWebIOClient({
        output_container_elem: $('#markdown-body'),
        input_container_elem: $('#input-cards'),
        backend_address: urlparams.get('pywebio_api') || '',
        app_name: urlparams.get('app') || 'index',
        protocol: "{{ protocol }}",
        runtime_config: {
            debug: urlparams.get('_pywebio_debug'),
            outputAnimation: !urlparams.get('_pywebio_disable_animate'),
            httpPullInterval: parseInt(urlparams.get('_pywebio_http_pull_interval') || 1000)
        },
    });
</script>
{% end %}
{% if js_code %}
<script>{% raw js_code %}</script>
{% end %}
</body>
</html>
