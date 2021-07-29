import pytest
import stripe

import subscriptions


def test_create_customer_user(user):
    assert user.stripe_customer_id is None
    subscriptions.create_customer(user)
    assert user.stripe_customer_id



def test_create_subscription_checkout_session(user_with_customer_id, stripe_price_id, checkout_success_url,
                                              checkout_cancel_url, payment_method_types):
    checkout = subscriptions.create_subscription_checkout(user_with_customer_id, stripe_price_id,
                                                          success_url=checkout_success_url,
                                                          cancel_url=checkout_cancel_url,
                                                          payment_method_types=payment_method_types)
    assert checkout['id'] is not None
    assert checkout['setup_intent'] is None
    assert checkout['success_url'] == checkout_success_url
    assert checkout['cancel_url'] == checkout_cancel_url


def test_create_checkout_session_no_customer_id_fails(user, stripe_price_id):
    with pytest.raises(subscriptions.StripeCustomerIdRequired):
        subscriptions.create_subscription_checkout(user, stripe_price_id)


def test_create_setup_checkout_session(user_with_customer_id, checkout_success_url,
                                       checkout_cancel_url, payment_method_types):
    checkout = subscriptions.create_setup_checkout(user_with_customer_id,
                                                   success_url=checkout_success_url,
                                                   cancel_url=checkout_cancel_url,
                                                   payment_method_types=payment_method_types)
    assert checkout['id'] is not None
    assert checkout['setup_intent'] is not None
    assert checkout['success_url'] == checkout_success_url
    assert checkout['cancel_url'] == checkout_cancel_url
    setup_intent = stripe.SetupIntent.retrieve(checkout['setup_intent'])
    assert 'subscription_id' not in setup_intent['metadata'] == {}


def test_create_setup_checkout_session_with_subscription(user_with_customer_id, checkout_success_url,
                                                         checkout_cancel_url, payment_method_types,
                                                         subscription):
    checkout = subscriptions.create_setup_checkout(user_with_customer_id,
                                                   subscription_id=subscription['id'],
                                                   success_url=checkout_success_url,
                                                   cancel_url=checkout_cancel_url,
                                                   payment_method_types=payment_method_types)
    assert checkout['id'] is not None
    assert checkout['setup_intent'] is not None
    assert checkout['success_url'] == checkout_success_url
    assert checkout['cancel_url'] == checkout_cancel_url
    setup_intent = stripe.SetupIntent.retrieve(checkout['setup_intent'])
    assert setup_intent['metadata']['subscription_id'] == subscription['id']


def test_is_subscribed(user_with_customer_id, subscription, stripe_subscription_product_id):
    is_subscribed = subscriptions.is_subscribed_and_cancelled_time(user_with_customer_id, stripe_subscription_product_id)
    assert is_subscribed['subscribed'] is True
    assert is_subscribed['cancel_at'] is None
    assert subscriptions.is_subscribed(user_with_customer_id, stripe_subscription_product_id)


def test_is_not_subscribed(no_user_and_user_with_and_without_customer_id, stripe_subscription_product_id):
    is_subscribed = subscriptions.is_subscribed_and_cancelled_time(no_user_and_user_with_and_without_customer_id,
                                                                   stripe_subscription_product_id)
    assert is_subscribed['subscribed'] is False
    assert is_subscribed['cancel_at'] is None
    assert subscriptions.is_subscribed(no_user_and_user_with_and_without_customer_id,
                                       stripe_subscription_product_id) is False


def test_is_subscribed_with_cache(user_with_customer_id, subscription, stripe_subscription_product_id, cache):
    cache_key = f'is_subscribed_{user_with_customer_id.id}_{stripe_subscription_product_id}'
    assert cache.get(cache_key) is None
    subscribed = subscriptions.is_subscribed_with_cache(user_with_customer_id, cache, stripe_subscription_product_id)
    assert subscribed is True
    assert cache.get(cache_key) is True
    subscribed = subscriptions.is_subscribed_with_cache(user_with_customer_id, cache, stripe_subscription_product_id)
    assert subscribed is True


def test_no_user_is_not_subscribed_with_cache(none_or_user, cache, stripe_subscription_product_id):
    subscribed = subscriptions.is_subscribed_with_cache(none_or_user, cache,
                                                        product_id=stripe_subscription_product_id)
    assert subscribed is False
    assert cache.data == {}


def test_is_not_subscribed_with_cache(user_with_customer_id, stripe_subscription_product_id, cache):
    cache_key = f'is_subscribed_{user_with_customer_id.id}_{stripe_subscription_product_id}'
    assert cache.get(cache_key) is None
    subscribed = subscriptions.is_subscribed_with_cache(user_with_customer_id, cache,
                                                        product_id=stripe_subscription_product_id)
    assert subscribed is False
    assert cache.get(cache_key) is None
    subscribed = subscriptions.is_subscribed_with_cache(user_with_customer_id, cache,
                                                        product_id=stripe_subscription_product_id)
    assert subscribed is False


def test_list_active_subscriptions_subscribed_user(user_with_customer_id,
                                                   subscription_current_period_end,
                                                   stripe_subscription_product_id,
                                                   stripe_price_id):
    subscribed_to = subscriptions.list_products_prices_subscribed_to(user_with_customer_id)
    assert subscribed_to == [
        {'product_id': stripe_subscription_product_id, 'price_id': stripe_price_id, 'cancel_at': None,
         'current_period_end': subscription_current_period_end}]


def test_list_active_subscriptions_user_with_customer_id(no_user_and_user_with_and_without_customer_id):
    is_subscribed = subscriptions.list_products_prices_subscribed_to(no_user_and_user_with_and_without_customer_id)
    assert is_subscribed == []


def test_get_subscription_prices(user_with_customer_id, subscription, expected_subscription_prices,
                                 stripe_subscription_product_id):
    prices = subscriptions.get_subscription_prices(user_with_customer_id, product=stripe_subscription_product_id)
    assert prices == expected_subscription_prices


def test_price_list_unsubscribed(no_user_and_user_with_and_without_customer_id, stripe_subscription_product_id,
                                 expected_subscription_prices_unsubscribed):
    result = subscriptions.get_subscription_prices(no_user_and_user_with_and_without_customer_id,
                                                   product=stripe_subscription_product_id)
    assert result == expected_subscription_prices_unsubscribed


def test_retrieve_price(user_with_customer_id, subscription, expected_subscription_prices,
                        stripe_price_id):
    prices = subscriptions.retrieve_price(user_with_customer_id, stripe_price_id)
    assert prices == expected_subscription_prices[0]


def test_get_subscription_products_and_prices(user_with_customer_id, expected_subscription_products_and_prices,
                                              subscription, stripe_subscription_product_id,
                                              stripe_unsubscribed_product_id):
    products = subscriptions.get_subscription_products_and_prices(user_with_customer_id,
                                                                  ids=[stripe_subscription_product_id,
                                                                       stripe_unsubscribed_product_id])
    assert products == expected_subscription_products_and_prices


def test_retrieve_product(user_with_customer_id, subscription, expected_subscription_products_and_prices,
                          stripe_subscription_product_id):
    prices = subscriptions.retrieve_product(user_with_customer_id, stripe_subscription_product_id)
    assert prices == expected_subscription_products_and_prices[1]


def test_product_list_unsubscribed(no_user_and_user_with_and_without_customer_id,
                                   stripe_subscription_product_id,
                                   stripe_unsubscribed_product_id,
                                   expected_subscription_products_and_prices_unsubscribed):
    result = subscriptions.get_subscription_products_and_prices(no_user_and_user_with_and_without_customer_id,
                                                                ids=[stripe_subscription_product_id,
                                                                     stripe_unsubscribed_product_id])
    assert result == expected_subscription_products_and_prices_unsubscribed


def test_allow_if_owned_by_user(user_with_customer_id, default_payment_method_saved):
    payment_method = subscriptions.allow_if_owned_by_user(user_with_customer_id, stripe.PaymentMethod,
                                                          default_payment_method_saved["id"], "detach")
    assert payment_method == default_payment_method_saved


def test_allow_if_owned_by_user_raises_error(wrong_customer_id, default_payment_method_saved):
    with pytest.raises(subscriptions.exceptions.StripeWrongCustomer):
        subscriptions.allow_if_owned_by_user(wrong_customer_id, stripe.PaymentMethod,
                                             default_payment_method_saved["id"], "detach")


@pytest.mark.parametrize('payment_types', [
    ["card"],
    ["card", "alipay"],
])
def test_list_payment_methods(user_with_customer_id, default_payment_method_saved, payment_method_saved, payment_types):
    payment_methods = subscriptions.list_payment_methods(
        user_with_customer_id, types=payment_types,
    )
    default_payment_method_saved['default'] = True
    payment_method_saved['default'] = False
    assert list(payment_methods) == [payment_method_saved, default_payment_method_saved]


@pytest.mark.parametrize('payment_types', [
    [],
    ["card"],
    ["card", "alipay"],
])
def list_payment_methods(none_or_user, payment_types):
    payment_methods = subscriptions.list_payment_methods(
        none_or_user, types=payment_types,
    )
    assert list(payment_methods) == []


def test_detach_payment_method(user_with_customer_id, default_payment_method_saved):
    payment_method = subscriptions.detach_payment_method(user_with_customer_id, default_payment_method_saved['id'])
    assert not payment_method['customer']


def test_detach_payment_method_wrong_customer(default_payment_method_saved, wrong_customer_id):
    with pytest.raises(subscriptions.exceptions.StripeWrongCustomer):
        subscriptions.detach_payment_method(wrong_customer_id, default_payment_method_saved['id'])


def test_detach_payment_method_no_customer_id(none_or_user, non_existing_payment_method_id):
    with pytest.raises(subscriptions.exceptions.StripeCustomerIdRequired):
        subscriptions.detach_payment_method(none_or_user, non_existing_payment_method_id)


def test_detach_all_payment_methods(user_with_customer_id, default_payment_method_saved):
    default_payment_method_saved["customer"] = None
    result = subscriptions.detach_all_payment_methods(user_with_customer_id, types=["card", "alipay"])
    assert result == [default_payment_method_saved]
    payment_method = stripe.PaymentMethod.retrieve(default_payment_method_saved["id"])
    assert payment_method["customer"] is None


def test_detach_all_payment_methods_none(no_user_and_user_with_and_without_customer_id):
    result = subscriptions.detach_all_payment_methods(no_user_and_user_with_and_without_customer_id,
                                                      types=["card", "alipay"])
    assert result == []


def test_update_default_payment_method_all_subscriptions(user_with_customer_id, payment_method_for_customer,
                                                         default_payment_method_for_customer, subscription):
    customer = stripe.Customer.retrieve(user_with_customer_id.stripe_customer_id)
    assert customer['invoice_settings']['default_payment_method'] == default_payment_method_for_customer['id']
    assert subscription['default_payment_method'] is None
    subscriptions.update_default_payment_method_all_subscriptions(user_with_customer_id,
                                                                  payment_method_for_customer["id"])
    customer = stripe.Customer.retrieve(user_with_customer_id.stripe_customer_id)
    assert customer['invoice_settings']['default_payment_method'] == payment_method_for_customer['id']
    subscription = stripe.Subscription.retrieve(subscription['id'])
    assert subscription['default_payment_method'] == payment_method_for_customer['id']


def test_create_setup_intent(user_with_customer_id, default_payment_method_saved):
    setup_intent = subscriptions.create_setup_intent(user_with_customer_id, payment_method_types=["card"])
    assert setup_intent['id'] is not None
    assert setup_intent['client_secret'] is not None
    assert setup_intent['payment_method_types'] == ['card']


def test_create_subscription(user_with_customer_id, default_payment_method_saved, stripe_price_id,
                             stripe_subscription_product_id):
    subscriptions.create_subscription(user_with_customer_id, stripe_price_id)
    response = subscriptions.is_subscribed_and_cancelled_time(user_with_customer_id, stripe_subscription_product_id)
    assert response['subscribed'] is True
    assert response['cancel_at'] is None
    customer = stripe.Customer.retrieve(user_with_customer_id.stripe_customer_id)
    assert customer['invoice_settings']['default_payment_method'] == default_payment_method_saved['id']


def test_create_subscription_set_default_payment_method(user_with_customer_id,
                                                        payment_method_for_customer,
                                                        default_payment_method_for_customer,
                                                        stripe_price_id,
                                                        stripe_subscription_product_id):
    customer = stripe.Customer.retrieve(user_with_customer_id.stripe_customer_id)
    assert customer['invoice_settings']['default_payment_method'] == default_payment_method_for_customer['id']
    sub = subscriptions.create_subscription(user_with_customer_id, stripe_price_id, set_as_default_payment_method=True,
                                            default_payment_method=payment_method_for_customer["id"])
    assert sub['default_payment_method'] == payment_method_for_customer["id"]
    customer = stripe.Customer.retrieve(user_with_customer_id.stripe_customer_id)
    assert customer['invoice_settings']['default_payment_method'] == payment_method_for_customer['id']
    response = subscriptions.is_subscribed_and_cancelled_time(user_with_customer_id, stripe_subscription_product_id)
    assert response['subscribed'] is True
    assert response['cancel_at'] is None


def test_create_subscription_set_default_but_no_payment_method(user_with_customer_id,
                                                               default_payment_method_for_customer,
                                                               stripe_price_id,
                                                               stripe_subscription_product_id):
    with pytest.raises(subscriptions.exceptions.DefaultPaymentMethodRequired):
        subscriptions.create_subscription(user_with_customer_id, stripe_price_id, set_as_default_payment_method=True)
    response = subscriptions.is_subscribed_and_cancelled_time(user_with_customer_id, stripe_subscription_product_id)
    assert response['subscribed'] is False
    assert response['cancel_at'] is None


def test_create_subscription_no_customer_id(none_or_user, stripe_price_id, stripe_subscription_product_id):
    with pytest.raises(subscriptions.exceptions.StripeCustomerIdRequired):
        subscriptions.create_subscription(none_or_user, stripe_price_id)
    response = subscriptions.is_subscribed_and_cancelled_time(none_or_user,
                                                              stripe_subscription_product_id)
    assert response['subscribed'] is False
    assert response['cancel_at'] is None


def test_cancel_subscription_for_product(user_with_customer_id, subscription, stripe_subscription_product_id):
    subscriptions.cancel_subscription_for_product(user_with_customer_id, stripe_subscription_product_id)
    response = subscriptions.is_subscribed_and_cancelled_time(user_with_customer_id, stripe_subscription_product_id)
    assert response['subscribed'] is False
    assert response['cancel_at'] is None


def test_cancel_subscription(user_with_customer_id, subscription, stripe_subscription_product_id):
    subscriptions.cancel_subscription(user_with_customer_id, subscription['id'])
    response = subscriptions.is_subscribed_and_cancelled_time(user_with_customer_id, stripe_subscription_product_id)
    assert response['subscribed'] is False
    assert response['cancel_at'] is None


def test_cancel_subscription_wrong_owner(subscription, wrong_customer_id):
    with pytest.raises(subscriptions.exceptions.StripeWrongCustomer):
        subscriptions.cancel_subscription(wrong_customer_id, subscription['id'])


def test_cancel_subscription_no_customer_id(none_or_user, non_existing_subscription_id):
    with pytest.raises(subscriptions.exceptions.StripeCustomerIdRequired):
        subscriptions.cancel_subscription(none_or_user, non_existing_subscription_id)


def test_modify_subscription_payment_method(user_with_customer_id, subscription, payment_method_saved,
                                            default_payment_method_saved):
    assert subscription['default_payment_method'] is None
    sub = subscriptions.modify_subscription(user_with_customer_id, subscription['id'],
                                            default_payment_method=payment_method_saved["id"])
    assert sub['default_payment_method'] == payment_method_saved["id"]
    customer = stripe.Customer.retrieve(user_with_customer_id.stripe_customer_id)
    assert customer['invoice_settings']['default_payment_method'] == default_payment_method_saved['id']


def test_modify_subscription_set_default_payment_method(user_with_customer_id,
                                                        payment_method_saved,
                                                        default_payment_method_for_customer,
                                                        subscription,
                                                        stripe_price_id,
                                                        stripe_subscription_product_id):
    assert subscription['default_payment_method'] is None
    subscriptions.modify_subscription(user_with_customer_id, subscription['id'], set_as_default_payment_method=True,
                                      default_payment_method=payment_method_saved["id"])
    sub = stripe.Subscription.retrieve(subscription['id'])
    assert sub['default_payment_method'] == payment_method_saved["id"]
    customer = stripe.Customer.retrieve(user_with_customer_id.stripe_customer_id)
    assert customer['invoice_settings']['default_payment_method'] == payment_method_saved['id']
    response = subscriptions.is_subscribed_and_cancelled_time(user_with_customer_id, stripe_subscription_product_id)
    assert response['subscribed'] is True
    assert response['cancel_at'] is None


def test_modify_subscription_wrong_owner(subscription, wrong_customer_id):
    with pytest.raises(subscriptions.exceptions.StripeWrongCustomer):
        subscriptions.modify_subscription(wrong_customer_id, subscription['id'])


def test_modify_subscription_no_customer_id(none_or_user, non_existing_subscription_id):
    with pytest.raises(subscriptions.exceptions.StripeCustomerIdRequired):
        subscriptions.modify_subscription(none_or_user, non_existing_subscription_id)


def test_subscription_lifecycle(user, stripe_price_id, stripe_subscription_product_id):
    subscriptions.create_customer(user)
    subscriptions.tests.create_default_payment_method_for_customer(user)
    subscriptions.create_subscription(user, stripe_price_id)
    response = subscriptions.is_subscribed_and_cancelled_time(user, stripe_subscription_product_id)
    assert response['subscribed'] is True
    assert response['cancel_at'] is None
    assert subscriptions.cancel_subscription_for_product(user, stripe_subscription_product_id)
    response = subscriptions.is_subscribed_and_cancelled_time(user, stripe_subscription_product_id)
    assert response['subscribed'] is False
    assert response['cancel_at'] is None
