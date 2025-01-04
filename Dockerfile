FROM ubuntu

WORKDIR /app

#Added to fix bug not allowing the docker image to be built
RUN apt-get -y update && apt-get -y install redis mysql-server libmysqlclient-dev python3-pip

COPY . .

#Added to fix bug not allowing the docker image to be built
RUN rm -rf /usr/lib/python3.*/EXTERNALLY-MANAGED && pip3 install --upgrade setuptools && pip3 install -r requirements_dev.txt --upgrade

ENV DEBIAN_FRONTEND="noninteractive" TZ="Africa/Johannesburg"

# Install necessary dependencies for starting mysql
RUN apt-get -y update && apt-get -y install make sudo mysql-server libmysqlclient-dev
RUN service mysql start && mysql mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY '';FLUSH PRIVILEGES;"

# Install remaining dependencies
RUN make install

# Make start script executable
RUN chmod +x start.sh

# Start MySQL and run server
CMD ["/bin/bash", "/app/start.sh"]
