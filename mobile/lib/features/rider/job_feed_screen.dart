import 'package:flutter/material.dart';

class RiderJobFeedScreen extends StatefulWidget {
  const RiderJobFeedScreen({super.key});

  @override
  State<RiderJobFeedScreen> createState() => _RiderJobFeedScreenState();
}

class _RiderJobFeedScreenState extends State<RiderJobFeedScreen> {
  // Toggle for Online/Offline status
  bool _isOnline = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rider Dashboard'),
        actions: [
          Switch(
            value: _isOnline,
            onChanged: (val) {
              setState(() {
                _isOnline = val;
              });
              // TODO: Call API to update availability
            },
            activeColor: Colors.green,
            inactiveThumbColor: Colors.grey,
          ),
        ],
      ),
      body: _isOnline 
          ? _buildJobFeed() 
          : _buildOfflineState(),
    );
  }

  Widget _buildOfflineState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.cloud_off, size: 64, color: Colors.grey),
          const SizedBox(height: 16),
          Text(
            'You are Offline',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          const Text('Go online to start receiving delivery requests.'),
        ],
      ),
    );
  }

  Widget _buildJobFeed() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: 3, // Mock data
      itemBuilder: (context, index) {
        return Card(
          margin: const EdgeInsets.only(bottom: 16),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'New Delivery Request',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Colors.orange,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const Text('3.5 km'),
                  ],
                ),
                const Divider(),
                const Text('Pickup: Spar (Borrowdale)'),
                const Text('Dropoff: 12 Kingsmead Road'),
                const SizedBox(height: 8),
                Text(
                  'Earnings: \$5.00',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.green[700],
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () {},
                        child: const Text('Decline'),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: FilledButton(
                        onPressed: () {
                          // TODO: Accept job API call
                        },
                        child: const Text('Accept Job'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
