FROM node:lts-alpine as build-stage
WORKDIR /app
COPY package*.json .
RUN npm install
COPY . .
# Budowanie aplikacji Vue (Vite)
RUN npm run build 

# ETAP 2: SERWOWANIE PLIKÓW PRZEZ NGINX
FROM nginx:stable-alpine as production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html
# Domyślnie Nginx nasłuchuje na porcie 80
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]