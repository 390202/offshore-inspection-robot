import { io } from 'socket.io-client'
export default io(window.location.origin, {
  autoConnect: false, reconnection: true, reconnectionDelay: 1000, timeout: 5000
})
