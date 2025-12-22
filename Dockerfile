# Step 1: Use Node.js to build the React app
FROM node:22-alpine AS build

ARG VITE_APP_API_BASE_URL
ENV VITE_APP_API_BASE_URL=${VITE_APP_API_BASE_URL}

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

RUN npm run build

# Step 2: Use Nginx to serve the built React app
FROM nginx:1.28-alpine

RUN apk add --no-cache fontconfig

COPY --from=build /app/dist /usr/share/nginx/html

RUN fc-cache -f -v

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
