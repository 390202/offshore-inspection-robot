const { Sequelize } = require('sequelize');

const sequelize = new Sequelize(
  process.env.DB_NAME || 'inspection_platform',
  process.env.DB_USER || 'inspection_app',
  process.env.DB_PASSWORD,
  {
  host: process.env.DB_HOST || '127.0.0.1',
  port: Number(process.env.DB_PORT || 5432),
  dialect: 'postgres',
  logging: false
});

module.exports = sequelize;
