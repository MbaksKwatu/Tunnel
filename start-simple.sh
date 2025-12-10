#!/bin/bash

echo "🚀 Starting FundIQ Simple Version (SQLite Backend)"
echo "================================================="

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Please run this from the Tunnel directory"
    exit 1
fi

# Start the simple backend
echo "🔧 Starting Simple Backend (SQLite)..."
cd backend
source venv/bin/activate
python simple_main.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Check if backend is running
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Backend started successfully"
else
    echo "❌ Backend failed to start"
    exit 1
fi

# Go back to main directory
cd ..

echo "🌐 Starting Frontend..."
echo "📱 Frontend will be available at: http://localhost:3000/simple-page"
echo "🔧 Backend API available at: http://localhost:8000"
echo ""
echo "🎯 To test:"
echo "   1. Open http://localhost:3000/simple-page"
echo "   2. Upload a PDF, CSV, or XLSX file"
echo "   3. Watch it get processed locally!"
echo ""
echo "Press Ctrl+C to stop both servers"

# Start frontend
npm run dev

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Stopping servers..."
    kill $BACKEND_PID 2>/dev/null
    exit 0
}

# Set up signal handling
trap cleanup SIGINT SIGTERM

# Wait for background process
wait $BACKEND_PID
