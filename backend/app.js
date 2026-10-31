const express = require('express');
const cors = require('cors');
const sequelize = require('./db');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const http = require('http');
const { Server } = require('socket.io');

const app = express();
app.use(cors());
app.use(express.json());

const SECRET_KEY = process.env.JWT_SECRET;
if (!SECRET_KEY) {
  throw new Error('JWT_SECRET environment variable is required');
}

// ================= 辅助函数：写系统日志 =================
const addLog = async (username, action, details) => {
  try {
    await sequelize.query(
      'INSERT INTO system_logs (username, action, details) VALUES (?, ?, ?)',
      { replacements: [username, action, details] }
    );
  } catch (error) { console.error('写入日志失败:', error); }
};

// ================= 数据库相关接口 =================
app.post('/api/register', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) return res.status(400).json({ code: 400, message: '用户名和密码不能为空' });
  try {
    const existingUser = await sequelize.query('SELECT * FROM users WHERE username = ?', { replacements: [username], type: sequelize.QueryTypes.SELECT });
    const user = Array.isArray(existingUser) ? existingUser[0] : existingUser;
    if (user) return res.status(400).json({ code: 400, message: '该用户名已被注册' });
    const salt = bcrypt.genSaltSync(10);
    const hashedPassword = bcrypt.hashSync(password, salt);
    await sequelize.query('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', { replacements: [username, hashedPassword, '运维人员'] });
    await addLog(username, '注册', '新用户注册成功');
    res.json({ code: 200, message: '注册成功！请登录' });
  } catch (error) { res.status(500).json({ code: 500, message: '注册失败，服务器错误' }); }
});

app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;
  try {
    const [results] = await sequelize.query('SELECT * FROM users WHERE username = ?', { replacements: [username], type: sequelize.QueryTypes.SELECT });
    const user = Array.isArray(results) ? results[0] : results;
    if (!user) return res.status(401).json({ code: 401, message: '用户不存在' });
    const isPasswordValid = bcrypt.compareSync(password, user.password);
    if (!isPasswordValid) return res.status(401).json({ code: 401, message: '密码错误' });
    const token = jwt.sign({ id: user.id, username: user.username, role: user.role }, SECRET_KEY, { expiresIn: '2h' });
    await addLog(username, '登录', '登录系统成功');
    res.json({ code: 200, message: '登录成功', data: { token, username: user.username, role: user.role } });
  } catch (error) { res.status(500).json({ code: 500, message: '服务器内部错误' }); }
});

app.get('/api/alarms', async (req, res) => {
  try {
    const alarms = await sequelize.query('SELECT * FROM alarms ORDER BY id DESC', { type: sequelize.QueryTypes.SELECT });
    res.json({ code: 200, data: alarms });
  } catch (error) { res.status(500).json({ code: 500, message: '获取告警失败' }); }
});

app.get('/api/logs', async (req, res) => {
  try {
    const logs = await sequelize.query('SELECT * FROM system_logs ORDER BY id DESC LIMIT 100', { type: sequelize.QueryTypes.SELECT });
    res.json({ code: 200, data: logs });
  } catch (error) { res.status(500).json({ code: 500, message: '获取日志失败' }); }
});

// These timestamp columns store UTC without a timezone; return an explicit instant.
const LORA_READING_COLUMNS = `id, device_id, sequence,
  mq3_state, mq6_state, mq8_state, mq3_raw, mq6_raw, mq8_raw,
  mq3_mv, mq6_mv, mq8_mv, status, remote,
  mq3_state AS mq5_state, mq3_raw AS mq5_raw, mq3_mv AS mq5_mv,
  created_at AT TIME ZONE 'UTC' AS created_at`;

app.get('/api/lora/latest', async (req, res) => {
  try {
    const rows = await sequelize.query(
      `SELECT ${LORA_READING_COLUMNS} FROM sensor_readings ORDER BY id DESC LIMIT 1`,
      { type: sequelize.QueryTypes.SELECT }
    );
    res.json({ code: 200, data: rows[0] || null });
  } catch (error) {
    res.status(500).json({ code: 500, message: '获取 LoRa 数据失败' });
  }
});

app.post('/api/lora/ingest', async (req, res) => {
  const { device_id, sequence, raw, sensor_mv = [0, 0, 0],
    threshold_alarm, status = 0, remote = '' } = req.body || {};
  if (!Number.isInteger(device_id) || device_id < 0 || device_id > 255 ||
      !Number.isInteger(sequence) || sequence < 0 || sequence > 65535 ||
      !Array.isArray(raw) || raw.length !== 3 ||
      !raw.every(value => value === 0 || value === 1) ||
      !Array.isArray(threshold_alarm) || threshold_alarm.length !== 3 ||
      !threshold_alarm.every((value, index) =>
        typeof value === 'boolean' && value === Boolean(raw[index])) ||
      !Array.isArray(sensor_mv) || sensor_mv.length !== 3 ||
      !sensor_mv.every(value => Number.isInteger(value) && value >= 0 && value <= 65535) ||
      !Number.isInteger(status) || status < 0 || status > 255 ||
      typeof remote !== 'string' || remote.length > 100) {
    return res.status(400).json({ code: 400, message: 'LoRa 数据格式错误' });
  }
  try {
    const rows = await sequelize.query(`
      INSERT INTO sensor_readings
        (device_id, sequence, mq3_state, mq6_state, mq8_state,
         mq3_raw, mq6_raw, mq8_raw, mq3_mv, mq6_mv, mq8_mv, status, remote)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      RETURNING ${LORA_READING_COLUMNS}
    `, {
      replacements: [device_id, sequence, ...raw, ...raw, ...sensor_mv, status, remote],
      type: sequelize.QueryTypes.SELECT
    });
    io.emit('lora_update', rows[0]);
    res.json({ code: 200, message: 'LoRa 数据已接收' });
  } catch (error) {
    console.error('LoRa 数据写库失败:', error);
    res.status(500).json({ code: 500, message: 'LoRa 数据写库失败' });
  }
});

// ================= 实时数据流与 WebSocket =================
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: '*' } });

let deviceState = {
  carA: { id: 'A', x: 15, y: 50, battery: 85, status: '巡检中', mileage: 1.2 },
  carB: { id: 'B', x: 180, y: 50, battery: 100, status: '待机', mileage: 0.0 },
  lora: { rssi: -65, snr: 8.5, packetLoss: 0.1 },
  station: { status: '待机', power: 0 },
  stats: { totalMileage: 1.2, coverage: 15, alarmCount: 0, handleRate: 85 },
  // 👇 核心：新增三种气体的真实模拟数据
  gas: {
    lpg: { name: '液化气 (LPG)', value: 15, unit: '%LEL', max: 100, threshold: 25 },
    helium: { name: '氦气 (He)', value: 0.5, unit: '%VOL', max: 100, threshold: 5 },
    hydrogen: { name: '氢气 (H2)', value: 8, unit: 'ppm', max: 100, threshold: 20 }
  }
};

// 核心模拟器：传感器波动、双机协同、位置更新
setInterval(() => {
  // 1. 小车A巡检逻辑
  if (deviceState.carA.status === '巡检中') {
    deviceState.carA.x += 1.5;
    if (deviceState.carA.x > 190) deviceState.carA.x = 10;
    deviceState.carA.mileage += 0.005;
    deviceState.carA.battery -= 0.05; 
    
    if (deviceState.carA.battery < 20 && deviceState.carB.status === '待机') {
      deviceState.carA.status = '返航充电';
      deviceState.carB.status = '前往接替';
      addLog('系统', '双机协同', `小车A电量低于20%，触发小车B前往接替`);
    }
  }

  // 2. 小车B接替逻辑
  if (deviceState.carB.status === '前往接替') {
    deviceState.carB.x -= 2; 
    if (deviceState.carB.x <= deviceState.carA.x) {
      deviceState.carB.status = '巡检中';
      deviceState.carA.status = '返航充电';
      deviceState.carB.mileage += 0.005;
      addLog('系统', '双机协同', `小车B已到达交接点，小车A开始返航充电`);
    }
  }

  // 3. 小车A返航充电逻辑
  if (deviceState.carA.status === '返航充电') {
    deviceState.carA.x += 2; 
    if (deviceState.carA.x >= 180) {
      deviceState.carA.x = 180;
      deviceState.carA.status = '充电中';
    }
  }

  // 4. 充电逻辑
  if (deviceState.carA.status === '充电中') {
    deviceState.carA.battery += 0.5;
    if (deviceState.carA.battery >= 90) {
      deviceState.carA.status = '待机';
      addLog('系统', '双机协同', `小车A充电完成，进入待机状态`);
    }
  }

  // 5. 保持小车B巡检移动
  if (deviceState.carB.status === '巡检中') {
    deviceState.carB.x += 1.5;
    if (deviceState.carB.x > 190) deviceState.carB.x = 10;
    deviceState.carB.mileage += 0.005;
    deviceState.carB.battery -= 0.02;
  }

  // 👇 6. 模拟气体传感器数值波动
  // 液化气波动范围：10 - 30
  deviceState.gas.lpg.value = Math.max(0, deviceState.gas.lpg.value + (Math.random() * 4 - 2));
  // 氦气波动范围：0.1 - 6
  deviceState.gas.helium.value = Math.max(0, deviceState.gas.helium.value + (Math.random() * 0.4 - 0.2));
  // 氢气波动范围：5 - 25
  deviceState.gas.hydrogen.value = Math.max(0, deviceState.gas.hydrogen.value + (Math.random() * 3 - 1.5));

  // 气体浓度超限触发告警
  Object.keys(deviceState.gas).forEach(key => {
    const gas = deviceState.gas[key];
    if (process.env.ENABLE_DEMO_GAS_ALARMS === 'true' &&
        gas.value > gas.threshold && Math.random() < 0.1) {
      const newAlarm = { id: Date.now(), level: '警告', time: new Date().toLocaleTimeString(), location: `${gas.name} 浓度超标`, status: '未处置' };
      deviceState.stats.alarmCount += 1;
      io.emit('new_alarm', newAlarm);
      sequelize.query('INSERT INTO alarms (level, time, location, status) VALUES (?, ?, ?, ?)', { replacements: [newAlarm.level, newAlarm.time, newAlarm.location, newAlarm.status] }).catch(err => console.error('写库失败', err));
    }
  });

  deviceState.lora.rssi = -60 - Math.floor(Math.random() * 10);
  deviceState.lora.snr = 8 + Math.random();
  deviceState.stats.totalMileage = (deviceState.carA.mileage + deviceState.carB.mileage).toFixed(2);
  const activeCar = deviceState.carB.status === '巡检中' ? deviceState.carB : deviceState.carA;
  deviceState.stats.coverage = Math.round((activeCar.x / 200) * 100);

  io.emit('device_update', { ...deviceState, timestamp: new Date().toLocaleTimeString() });
}, 1000);

io.on('connection', (socket) => {
  socket.on('handle_alarm', async (data) => {
    const { alarmId, action, username } = data;
    try {
      const newStatus = action === 'confirm' ? '已确认' : '处置中';
      await sequelize.query('UPDATE alarms SET status = ? WHERE id = ?', { replacements: [newStatus, alarmId] });
      
      if (action === 'dispatch') {
        const activeCar = deviceState.carB.status === '巡检中' ? deviceState.carB : deviceState.carA;
        activeCar.status = '前往处置';
        activeCar.x = 120; 
        io.emit('device_update', { ...deviceState, timestamp: new Date().toLocaleTimeString() });
        await addLog(username || '运维人员', '下发指令', `对告警 ${alarmId} 下发处置指令，小车前往漏点`);
      } else if (action === 'confirm') {
        await addLog(username || '运维人员', '确认告警', `确认告警 ${alarmId}`);
      }
      io.emit('alarm_status_update', { id: alarmId, status: newStatus });
    } catch (error) { console.error(error); }
  });

  socket.on('dispatch_task', async (data) => {
    const { taskId, route, car, username } = data;
    try {
      if (car === '小车 A') { deviceState.carA.status = '执行任务'; deviceState.carA.x = 50; }
      else if (car === '小车 B') { deviceState.carB.status = '执行任务'; deviceState.carB.x = 50; }
      await addLog(username || '运维人员', '下发任务', `任务 ${taskId} (${route}) 已下发给 ${car}`);
      io.emit('device_update', { ...deviceState, timestamp: new Date().toLocaleTimeString() });
      io.emit('task_status_update', { taskId, status: '执行中' });
    } catch (error) { console.error('下发任务失败:', error); }
  });
});

// ================= 启动服务器与初始化数据 =================
const PORT = Number(process.env.PORT || 3000);

sequelize.authenticate()
  .then(async () => {
    console.log('✅ 数据库连接成功！');
    
    await sequelize.query(`
      CREATE TABLE IF NOT EXISTS system_logs (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50),
        action VARCHAR(100),
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    await sequelize.query(`
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL,
        password TEXT NOT NULL, role VARCHAR(50) DEFAULT '运维人员',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    await sequelize.query(`
      CREATE TABLE IF NOT EXISTS alarms (
        id SERIAL PRIMARY KEY, level VARCHAR(20), time VARCHAR(30),
        location VARCHAR(100), status VARCHAR(20),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    await sequelize.query(`
      CREATE TABLE IF NOT EXISTS sensor_readings (
        id SERIAL PRIMARY KEY, device_id INTEGER NOT NULL, sequence INTEGER NOT NULL,
        mq3_state INTEGER NOT NULL DEFAULT 0, mq6_state INTEGER NOT NULL DEFAULT 0,
        mq8_state INTEGER NOT NULL DEFAULT 0, mq3_raw INTEGER NOT NULL DEFAULT 0,
        mq6_raw INTEGER NOT NULL DEFAULT 0, mq8_raw INTEGER NOT NULL DEFAULT 0,
        mq3_mv INTEGER NOT NULL DEFAULT 0, mq6_mv INTEGER NOT NULL DEFAULT 0,
        mq8_mv INTEGER NOT NULL DEFAULT 0, status INTEGER NOT NULL DEFAULT 0,
        remote VARCHAR(100), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    const [results] = await sequelize.query('SELECT COUNT(*) as count FROM alarms');
    if (process.env.ENABLE_DEMO_GAS_ALARMS === 'true' && Number(results[0].count) === 0) {
      await sequelize.query("INSERT INTO alarms (level, time, location, status) VALUES ('警告', '12:35:20', 'X:102, Y:45', '未处置'), ('确认', '12:30:10', 'X:50, Y:20', '已确认')");
    }
    
    server.listen(PORT, () => {
      console.log(`后端服务器已启动: http://localhost:${PORT}`);
    });
  })
  .catch(err => { console.error('❌ 数据库连接失败：', err); process.exit(1); });
