FROM node:22-alpine AS dev

WORKDIR /app

COPY package.json ./
RUN npm install --legacy-peer-deps

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


FROM node:22-alpine AS build

WORKDIR /app
COPY package.json ./
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build


FROM nginx:1.27-alpine AS prod

COPY --from=build /app/dist /usr/share/nginx/html

RUN printf 'server {\n  listen 80;\n  root /usr/share/nginx/html;\n  index index.html;\n  add_header X-Frame-Options "DENY" always;\n  add_header X-Content-Type-Options "nosniff" always;\n  add_header Referrer-Policy "no-referrer" always;\n  location / { try_files $uri /index.html; }\n}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
