import subscriptions
import pytest


def test_00_create_customer_new_user(new_user):
    assert new_user.stripe_customer_id is None
    subscriptions.create_customer(new_user)
    assert new_user.stripe_customer_id


def test_01_create_checkout_session_existing_user(existing_user, stripe_monthly_price_id, stripe_existing_customer_id):
    checkout = subscriptions.create_stripe_subscription_checkout(existing_user, stripe_monthly_price_id)
    assert stripe_existing_customer_id == existing_user.stripe_customer_id
    assert checkout['id'] is not None


def test_02_create_checkout_session_no_customer_fails(new_user, stripe_monthly_price_id):
    with pytest.raises(subscriptions.StripeCustomerIdRequired):
        subscriptions.create_stripe_subscription_checkout(new_user, stripe_monthly_price_id)


def test_03_create_customer_portal_existing_user(existing_user, stripe_existing_customer_id):
    checkout = subscriptions.create_billing_portal_session(existing_user)
    assert stripe_existing_customer_id == existing_user.stripe_customer_id
    assert checkout['url'] is not None


def test_04_create_customer_portal_no_customer_fails(new_user):
    with pytest.raises(subscriptions.StripeCustomerIdRequired):
        subscriptions.create_billing_portal_session(new_user)


def test_05_is_subscribed_existing_user(existing_user, stripe_subscription_product_id):
    is_subscribed = subscriptions.is_subscribed_and_cancelled_time(existing_user, stripe_subscription_product_id)
    assert is_subscribed['subscribed'] is True
    assert is_subscribed['cancel_at'] is None
    assert subscriptions.is_subscribed(existing_user, stripe_subscription_product_id)


def test_06_is_not_subscribed_new_user(new_user, stripe_subscription_product_id):
    is_subscribed = subscriptions.is_subscribed_and_cancelled_time(new_user, stripe_subscription_product_id)
    assert is_subscribed['subscribed'] is False
    assert is_subscribed['cancel_at'] is None
    assert subscriptions.is_subscribed(new_user, stripe_subscription_product_id) is False


def test_07_is_subscribed_with_cache_existing_user(existing_user, stripe_subscription_product_id, cache):
    cache_key = f'is_subscribed_{existing_user.id}'
    assert cache.get(cache_key) is None
    subscribed = subscriptions.is_subscribed_with_cache(existing_user, stripe_subscription_product_id, cache)
    assert subscribed is True
    assert cache.get(cache_key) is True
    subscribed = subscriptions.is_subscribed_with_cache(existing_user, stripe_subscription_product_id, cache)
    assert subscribed is True


def test_08_is_not_subscribed_with_cache_new_user(new_user, stripe_subscription_product_id, cache):
    cache_key = f'is_subscribed_{new_user.id}'
    assert cache.get(cache_key) is None
    subscribed = subscriptions.is_subscribed_with_cache(new_user, stripe_subscription_product_id, cache)
    assert subscribed is False
    assert cache.get(cache_key) is None
    subscribed = subscriptions.is_subscribed_with_cache(new_user, stripe_subscription_product_id, cache)
    assert subscribed is False


def test_09_user_exists_on_stripe_not_subscribed(new_user, stripe_subscription_product_id):
    subscriptions.create_customer(new_user)
    assert new_user.stripe_customer_id is not None
    is_subscribed = subscriptions.is_subscribed_and_cancelled_time(new_user, stripe_subscription_product_id)
    assert is_subscribed['subscribed'] is False
    assert is_subscribed['cancel_at'] is None


def test_10_list_active_subscriptions_existing_user(existing_user, stripe_subscription_product_id):
    is_subscribed = subscriptions.list_products_subscribed_to(existing_user)
    assert is_subscribed == [(stripe_subscription_product_id, None)]


def test_11_list_active_subscriptions_new_user(new_user):
    is_subscribed = subscriptions.list_products_subscribed_to(new_user)
    assert is_subscribed == []


def test_12_list_prices_subscribed_to_existing_user(existing_user, stripe_monthly_price_id):
    is_subscribed = subscriptions.list_prices_subscribed_to(existing_user)
    assert is_subscribed == [stripe_monthly_price_id]


def test_13_list_prices_subscribed_to_new_user(new_user):
    is_subscribed = subscriptions.list_prices_subscribed_to(new_user)
    assert is_subscribed == []


def test_14_subscription_lifecycle(new_user, stripe_monthly_price_id, stripe_subscription_product_id):
    subscriptions.create_customer(new_user)
    subscriptions.tests.create_payment_method(new_user)
    subscriptions.create_subscription(new_user, stripe_monthly_price_id)
    response = subscriptions.is_subscribed_and_cancelled_time(new_user, stripe_subscription_product_id)
    assert response['subscribed'] is True
    assert response['cancel_at'] is None
    assert subscriptions.cancel_subscription(new_user, stripe_subscription_product_id)
    response = subscriptions.is_subscribed_and_cancelled_time(new_user, stripe_subscription_product_id)
    assert response['subscribed'] is False
    assert response['cancel_at'] is None
