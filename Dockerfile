FROM nginx:1.27-alpine

# Only the nginx template is baked into the image. HTML and JSON are supplied
# by the bind mount, so they can be replaced without rebuilding the image.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# The official nginx entrypoint substitutes only CAMERA_* and API_* variables.
# This keeps nginx variables such as $host untouched.
# Loopback camera fallback is a non-secret placeholder; override it in .env.
# The API fallback is the Compose service name used by the same stack.
ENV CAMERA_URL=http://127.0.0.1:8080/video \
    API_UPSTREAM=http://gledopto-api:8000/api/ \
    NGINX_ENVSUBST_FILTER="^(CAMERA_|API_)"

EXPOSE 80
