import pytest
import subscriptions


def test_create_customer_user(user):
    assert user.stripe_customer_id is None
    subscriptions.create_customer(user)
    assert user.stripe_customer_id


def test_create_checkout_session(user_with_customer_id, stripe_price_id, checkout_success_url,
                                 checkout_cancel_url, payment_method_types):
    checkout = subscriptions.create_subscription_checkout(user_with_customer_id, stripe_price_id,
                                                          success_url=checkout_success_url,
                                                          cancel_url=checkout_cancel_url,
                                                          payment_method_types=payment_method_types)
    assert checkout['id'] is not None
    assert checkout['success_url'] == checkout_success_url
    assert checkout['cancel_url'] == checkout_cancel_url


def test_create_checkout_session_no_customer_id_fails(user, stripe_price_id):
    with pytest.raises(subscriptions.StripeCustomerIdRequired):
        subscriptions.create_subscription_checkout(user, stripe_price_id)


def test_is_subscribed(subscribed_user, stripe_subscription_product_id):
    is_subscribed = subscriptions.is_subscribed_and_cancelled_time(subscribed_user, stripe_subscription_product_id)
    assert is_subscribed['subscribed'] is True
    assert is_subscribed['cancel_at'] is None
    assert subscriptions.is_subscribed(subscribed_user, stripe_subscription_product_id)


def test_is_not_subscribed_user(user_with_customer_id, stripe_subscription_product_id):
    is_subscribed = subscriptions.is_subscribed_and_cancelled_time(user_with_customer_id, stripe_subscription_product_id)
    assert is_subscribed['subscribed'] is False
    assert is_subscribed['cancel_at'] is None
    assert subscriptions.is_subscribed(user_with_customer_id, stripe_subscription_product_id) is False


def test_is_not_subscribed_user_no_customer_id(user, stripe_subscription_product_id):
    is_subscribed = subscriptions.is_subscribed_and_cancelled_time(user, stripe_subscription_product_id)
    assert is_subscribed['subscribed'] is False
    assert is_subscribed['cancel_at'] is None
    assert subscriptions.is_subscribed(user, stripe_subscription_product_id) is False


def test_is_subscribed_with_cache(subscribed_user, stripe_subscription_product_id, cache):
    cache_key = f'is_subscribed_{stripe_subscription_product_id}_{subscribed_user.id}'
    assert cache.get(cache_key) is None
    subscribed = subscriptions.is_subscribed_with_cache(subscribed_user, cache, stripe_subscription_product_id)
    assert subscribed is True
    assert cache.get(cache_key) is True
    subscribed = subscriptions.is_subscribed_with_cache(subscribed_user, cache, stripe_subscription_product_id)
    assert subscribed is True


def test_is_not_subscribed_with_cache(user, stripe_subscription_product_id, cache):
    cache_key = f'is_subscribed_{user.id}'
    assert cache.get(cache_key) is None
    subscribed = subscriptions.is_subscribed_with_cache(user, cache, product_id=stripe_subscription_product_id)
    assert subscribed is False
    assert cache.get(cache_key) is None
    subscribed = subscriptions.is_subscribed_with_cache(user, cache, product_id=stripe_subscription_product_id)
    assert subscribed is False


def test_list_active_subscriptions_subscribed_user(subscribed_user, stripe_subscription_product_id):
    subscribed_to = subscriptions.list_products_subscribed_to(subscribed_user)
    assert subscribed_to == [{'product_id': stripe_subscription_product_id, 'cancel_at': None}]


def test_list_active_subscriptions_user_no_customer_id(user):
    is_subscribed = subscriptions.list_products_subscribed_to(user)
    assert is_subscribed == []


def test_list_active_subscriptions_user_with_customer_id(user_with_customer_id):
    is_subscribed = subscriptions.list_products_subscribed_to(user_with_customer_id)
    assert is_subscribed == []


def test_list_prices_subscribed_to_subscribed_user(subscribed_user, stripe_price_id):
    subscribed_to = subscriptions.list_prices_subscribed_to(subscribed_user)
    assert subscribed_to == [{'cancel_at': None, 'price_id': stripe_price_id}]


def test_list_prices_subscribed_to_user_no_subscriptions(user):
    is_subscribed = subscriptions.list_prices_subscribed_to(user)
    assert is_subscribed == []


def test_get_subscription_prices(subscribed_user, expected_subscription_prices, stripe_subscription_product_id):
    prices = subscriptions.get_subscription_prices(subscribed_user, product=stripe_subscription_product_id)
    assert prices == expected_subscription_prices


def test_get_subscription_products_and_prices(subscribed_user, expected_subscription_products_and_prices,
                                              stripe_subscription_product_id, stripe_unsubscribed_product_id):
    products = subscriptions.get_subscription_products_and_prices(subscribed_user,
                                                                  ids=[stripe_subscription_product_id,
                                                                       stripe_unsubscribed_product_id])
    assert products == expected_subscription_products_and_prices


def test_subscription_lifecycle(user, stripe_price_id, stripe_subscription_product_id):
    subscriptions.create_customer(user)
    subscriptions.tests.create_payment_method(user)
    subscriptions.create_subscription(user, stripe_price_id)
    response = subscriptions.is_subscribed_and_cancelled_time(user, stripe_subscription_product_id)
    assert response['subscribed'] is True
    assert response['cancel_at'] is None
    assert subscriptions.cancel_subscription(user, stripe_subscription_product_id)
    response = subscriptions.is_subscribed_and_cancelled_time(user, stripe_subscription_product_id)
    assert response['subscribed'] is False
    assert response['cancel_at'] is None
