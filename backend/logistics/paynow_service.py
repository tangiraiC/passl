from paynow import Paynow
from django.conf import settings
import logging

# Using mock credentials for dev if not provided
PAYNOW_INTEGRATION_ID = getattr(settings, 'PAYNOW_INTEGRATION_ID', '99999')
PAYNOW_INTEGRATION_KEY = getattr(settings, 'PAYNOW_INTEGRATION_KEY', '12345678')

logger = logging.getLogger(__name__)

class PaynowService:
    def __init__(self):
        self.paynow = Paynow(
            PAYNOW_INTEGRATION_ID,
            PAYNOW_INTEGRATION_KEY,
            'http://google.com', # Return URL
            'http://google.com'  # Result/Webhook URL
        )

    def initiate_payment(self, order, email):
        """
        Create a new payment in Paynow
        """
        payment = self.paynow.create_payment(f'Order #{order.id}', email)
        
        # Add items to payment
        # For simplicity, adding one line item for the total
        payment.add('Order Total', float(order.total_amount))

        try:
            response = self.paynow.send(payment)
            if response.success:
                return {
                    'success': True,
                    'poll_url': response.poll_url,
                    'redirect_url': response.redirect_url,
                    'instructions': response.instructions
                }
            else:
                return {'success': False, 'error': "Paynow error"}
        except Exception as e:
            logger.error(f"Paynow Exception: {e}")
            return {'success': False, 'error': str(e)}

    def check_status(self, poll_url):
        """
        Check the status of a transaction
        """
        status = self.paynow.check_transaction_status(poll_url)
        return status.status
